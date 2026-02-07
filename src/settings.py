import argparse
import os
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = os.getenv("RADAR_OUTPUT_DIR", "output")
OUTPUT_DIR = str((REPO_ROOT / DEFAULT_OUTPUT_DIR).resolve())
DB_PATH = os.getenv("RADAR_DB_PATH", str((Path(OUTPUT_DIR) / "radar.db").resolve()))
OUT_HTML = os.getenv(
    "RADAR_DASHBOARD_PATH",
    str((Path(OUTPUT_DIR) / "dashboard_v04.html").resolve()),
)
HALF_LIFE_DAYS = float(os.getenv("RADAR_EVENT_HALF_LIFE_DAYS", "7"))
REPORT_DIR = str((Path(OUTPUT_DIR) / "reports").resolve())


def ensure_output_dirs() -> None:
    Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
    Path(REPORT_DIR).mkdir(parents=True, exist_ok=True)


def add_common_args(parser: argparse.ArgumentParser, include_half_life: bool = False) -> None:
    parser.add_argument(
        "--output-dir",
        default=os.getenv("RADAR_OUTPUT_DIR", "output"),
        help="Output directory for generated artifacts (default: output)",
    )
    if include_half_life:
        parser.add_argument(
            "--half-life-days",
            type=float,
            default=float(os.getenv("RADAR_EVENT_HALF_LIFE_DAYS", "7")),
            help="Half-life days for event decay (default: 7)",
        )


def from_args(args):
    output_dir = str((REPO_ROOT / args.output_dir).resolve())
    db_path = str((Path(output_dir) / "radar.db").resolve())
    out_html = str((Path(output_dir) / "dashboard_v04.html").resolve())
    half_life_days = float(getattr(args, "half_life_days", HALF_LIFE_DAYS))
    report_dir = str((Path(output_dir) / "reports").resolve())
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    Path(report_dir).mkdir(parents=True, exist_ok=True)
    return {
        "output_dir": output_dir,
        "db_path": db_path,
        "out_html": out_html,
        "half_life_days": half_life_days,
        "report_dir": report_dir,
    }
