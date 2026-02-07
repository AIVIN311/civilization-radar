import subprocess
import sys
import argparse
from pathlib import Path

def run(cmd):
    print("\n>>", " ".join(cmd))
    r = subprocess.run(cmd, shell=False)
    if r.returncode != 0:
        raise SystemExit(r.returncode)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="output")
    parser.add_argument("--half-life-days", type=float, default=7.0)
    parser.add_argument("--input-snapshots", default="input/snapshots.jsonl")
    parser.add_argument("--input-daily", default=None)
    args = parser.parse_args()

    py = sys.executable
    common = ["--output-dir", args.output_dir]

    run([py, "scripts/apply_sql_migrations.py", *common])
    run([py, "seed_from_snapshots.py", "--input", args.input_snapshots, *common])
    run([py, "upgrade_to_v02.py", *common])

    daily_input = args.input_daily
    if daily_input is None:
        candidate = Path(args.output_dir) / "daily_snapshots.jsonl"
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

    print(f"\nOK: pipeline done. Open {args.output_dir}/dashboard_v04.html")

if __name__ == "__main__":
    main()
