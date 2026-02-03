import subprocess
import sys

def run(cmd):
    print("\n>>", " ".join(cmd))
    r = subprocess.run(cmd, shell=False)
    if r.returncode != 0:
        raise SystemExit(r.returncode)

def main():
    py = sys.executable

    run([py, "gen_snapshots_50.py"])
    run([py, "seed_from_snapshots.py"])
    run([py, "upgrade_to_v02.py"])
    # 你如果檔名不同，改這行
    run([py, "render_dashboard_v02.py"])

    print("\nOK: pipeline done. Open dashboard_v02.html")

if __name__ == "__main__":
    main()
