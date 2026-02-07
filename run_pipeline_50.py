import argparse
import json
import os
import shutil
import stat
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def run(cmd):
    print("\n>>", " ".join(cmd))
    r = subprocess.run(cmd, shell=False)
    if r.returncode != 0:
        raise SystemExit(r.returncode)


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


def make_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def promote_to_latest(run_dir: Path, output_root: Path, run_id: str):
    latest = output_root / "latest"
    tmp = output_root / "tmp" / f"latest_tmp_{run_id}"
    backup = output_root / "tmp" / f"latest_bak_{run_id}"

    safe_rmtree(tmp)
    safe_rmtree(backup)
    shutil.copytree(run_dir, tmp)

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


def write_run_report(run_dir: Path, output_root: Path, run_id: str):
    reports_dir = output_root / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    eval_src = run_dir / "reports" / "eval_quality.json"
    if eval_src.exists():
        shutil.copy2(eval_src, reports_dir / f"eval_quality_{run_id}.json")

    payload = {
        "run_id": run_id,
        "run_dir": str(run_dir),
        "latest_dir": str(output_root / "latest"),
        "dashboard": str(output_root / "latest" / "dashboard_v04.html"),
        "db": str(output_root / "latest" / "radar.db"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    (reports_dir / f"run_{run_id}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def unique_run_dir(output_root: Path, run_id: str) -> Path:
    runs_dir = output_root / "runs"
    run_dir = runs_dir / run_id
    idx = 1
    while run_dir.exists():
        run_dir = runs_dir / f"{run_id}_{idx:02d}"
        idx += 1
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_dir


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        default="output",
        help="Output root directory that contains latest/runs/reports/tmp (default: output)",
    )
    parser.add_argument("--half-life-days", type=float, default=7.0)
    parser.add_argument("--input-snapshots", default="input/snapshots.jsonl")
    parser.add_argument("--input-daily", default=None)
    args = parser.parse_args()

    output_root = Path(args.output_dir).resolve()
    ensure_layout(output_root)
    run_id = make_run_id()
    run_dir = unique_run_dir(output_root, run_id)

    py = sys.executable
    common = ["--output-dir", str(run_dir)]

    run([py, "scripts/apply_sql_migrations.py", *common])
    run([py, "seed_from_snapshots.py", "--input", args.input_snapshots, *common])
    run([py, "upgrade_to_v02.py", *common])

    daily_input = args.input_daily
    if daily_input is None:
        candidate = run_dir / "daily_snapshots.jsonl"
        if candidate.exists():
            daily_input = str(candidate)
        else:
            daily_input = args.input_snapshots

    run([py, "scripts/derive_events_from_daily.py", "--input", daily_input, *common])
    run([py, "scripts/load_events_into_db.py", *common])
    run([py, "build_chain_matrix_v10.py", "--half-life-days", str(args.half_life_days), *common])
    run([py, "upgrade_to_v03_chain.py", *common])
    run([py, "render_dashboard_v02.py", "--half-life-days", str(args.half_life_days), *common])
    run([py, "scripts/eval_quality.py", *common])

    promote_to_latest(run_dir, output_root, run_id)
    write_run_report(run_dir, output_root, run_id)

    print(f"\nOK: pipeline done. Open {output_root / 'latest' / 'dashboard_v04.html'}")


if __name__ == "__main__":
    main()
