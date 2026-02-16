import argparse
import json
import os
import shutil
import stat
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable


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
    args = parser.parse_args()

    output_root = (ROOT / args.output_root).resolve()
    ensure_layout(output_root)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    cmd = [PY, "scripts/run_acceptance_v04.py", "--output-root", str(output_root)]
    print(">>", " ".join(cmd))
    r = subprocess.run(cmd, cwd=ROOT)
    if r.returncode != 0:
        raise SystemExit(r.returncode)

    source = output_root / "accept_run1"
    if not source.exists():
        raise SystemExit(f"missing acceptance source directory: {source}")

    promote_to_latest(source, output_root, stamp)

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
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
