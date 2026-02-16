import argparse
import json
import os
import re
import shutil
import stat
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"


def detect_ci_acceptance_contract() -> dict:
    if not CI_WORKFLOW.exists():
        return {
            "target": "unknown",
            "skip_v04_hash": None,
            "source": str(CI_WORKFLOW),
            "reason": "missing_ci_workflow",
        }
    text = CI_WORKFLOW.read_text(encoding="utf-8")
    found = []

    m_v07 = re.search(r"run_acceptance_v07\.py([^\r\n]*)", text)
    if m_v07:
        found.append(
            {
                "target": "v07",
                "skip_v04_hash": "--skip-v04-hash" in str(m_v07.group(1) or ""),
                "source": str(CI_WORKFLOW),
                "reason": "matched_v07",
            }
        )

    m_v04 = re.search(r"run_acceptance_v04\.py([^\r\n]*)", text)
    if m_v04:
        found.append(
            {
                "target": "v04",
                "skip_v04_hash": None,
                "source": str(CI_WORKFLOW),
                "reason": "matched_v04",
            }
        )

    if not found:
        return {
            "target": "unknown",
            "skip_v04_hash": None,
            "source": str(CI_WORKFLOW),
            "reason": "no_acceptance_command_match",
        }
    if len(found) > 1:
        return {
            "target": "mixed",
            "skip_v04_hash": None,
            "source": str(CI_WORKFLOW),
            "reason": "multiple_acceptance_commands_detected",
        }
    return found[0]


def ensure_ci_promote_alignment(target: str, skip_v04_hash: bool, allow_mismatch: bool) -> dict:
    ci = detect_ci_acceptance_contract()
    ci_target = str(ci.get("target") or "unknown")
    ci_skip = ci.get("skip_v04_hash")

    if allow_mismatch:
        return ci

    if ci_target in ("v04", "v07") and ci_target != target:
        raise SystemExit(
            "CI/promote acceptance mismatch: "
            f"ci_target={ci_target}, promote_target={target}. "
            "Use --allow-ci-mismatch to override explicitly."
        )
    if target == "v07" and isinstance(ci_skip, bool) and ci_skip != bool(skip_v04_hash):
        raise SystemExit(
            "CI/promote acceptance mismatch: "
            f"ci_skip_v04_hash={ci_skip}, promote_skip_v04_hash={skip_v04_hash}. "
            "Use --allow-ci-mismatch to override explicitly."
        )
    return ci


def _on_rm_error(func, path, exc_info):
    try:
        os.chmod(path, stat.S_IWRITE)
    except Exception:
        pass
    func(path)


def safe_rmtree(path: Path):
    if not path.exists():
        return
    shutil.rmtree(path, onerror=_on_rm_error)


def ensure_layout(output_root: Path):
    (output_root / "latest").mkdir(parents=True, exist_ok=True)
    (output_root / "runs").mkdir(parents=True, exist_ok=True)
    (output_root / "reports").mkdir(parents=True, exist_ok=True)
    (output_root / "tmp").mkdir(parents=True, exist_ok=True)


def promote_to_latest(source_dir: Path, output_root: Path, stamp: str):
    latest = output_root / "latest"
    tmp = output_root / "tmp" / f"latest_tmp_{stamp}"
    backup = output_root / "tmp" / f"latest_bak_{stamp}"

    safe_rmtree(tmp)
    safe_rmtree(backup)
    shutil.copytree(source_dir, tmp)

    moved_old = False
    if latest.exists():
        try:
            os.replace(str(latest), str(backup))
            moved_old = True
        except Exception:
            safe_rmtree(latest)

    try:
        os.replace(str(tmp), str(latest))
    except Exception:
        if latest.exists():
            safe_rmtree(latest)
        shutil.move(str(tmp), str(latest))

    if moved_old and backup.exists():
        safe_rmtree(backup)
    if tmp.exists():
        safe_rmtree(tmp)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", default="output")
    parser.add_argument(
        "--legacy-v04",
        action="store_true",
        help="Run v0.4 acceptance path instead of default v0.7 path.",
    )
    parser.add_argument(
        "--full-v07",
        action="store_true",
        help="Run full v0.7 acceptance (do not skip v0.4 hash gate).",
    )
    parser.add_argument(
        "--skip-v05",
        action="store_true",
        help="Forward --skip-v05 to run_acceptance_v07.py.",
    )
    parser.add_argument(
        "--allow-ci-mismatch",
        action="store_true",
        help="Allow promote acceptance mode to differ from CI acceptance contract.",
    )
    args = parser.parse_args()

    output_root = (ROOT / args.output_root).resolve()
    ensure_layout(output_root)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = "v04" if args.legacy_v04 else "v07"
    skip_v04_hash = bool((not args.legacy_v04) and (not args.full_v07))
    ci_contract = ensure_ci_promote_alignment(
        target=target,
        skip_v04_hash=skip_v04_hash,
        allow_mismatch=bool(args.allow_ci_mismatch),
    )

    if args.legacy_v04:
        cmd = [PY, "scripts/run_acceptance_v04.py", "--output-root", str(output_root)]
        source = output_root / "accept_run1"
    else:
        acceptance_root = output_root / "acceptance_v07"
        cmd = [PY, "scripts/run_acceptance_v07.py", "--output-root", str(acceptance_root)]
        if skip_v04_hash:
            cmd.append("--skip-v04-hash")
        if args.skip_v05:
            cmd.append("--skip-v05")
        source = acceptance_root / "run_tw_a" / "latest"

    print(">>", " ".join(cmd))
    r = subprocess.run(cmd, cwd=ROOT)
    if r.returncode != 0:
        raise SystemExit(r.returncode)

    if not source.exists():
        raise SystemExit(f"missing acceptance source directory: {source}")

    promote_to_latest(source, output_root, stamp)

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "acceptance_target": target,
        "acceptance_cmd": cmd,
        "skip_v04_hash": skip_v04_hash if target == "v07" else None,
        "ci_acceptance_target": ci_contract.get("target"),
        "ci_skip_v04_hash": ci_contract.get("skip_v04_hash"),
        "ci_contract_source": ci_contract.get("source"),
        "ci_contract_reason": ci_contract.get("reason"),
        "source": str(source),
        "latest": str(output_root / "latest"),
        "dashboard": str(output_root / "latest" / "dashboard_v04.html"),
        "db": str(output_root / "latest" / "radar.db"),
    }
    report_path = output_root / "reports" / f"acceptance_latest_{stamp}.json"
    report_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK: latest refreshed from acceptance output -> {output_root / 'latest'}")
    print(f"Report: {report_path}")


if __name__ == "__main__":
    main()
