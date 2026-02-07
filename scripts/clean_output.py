import argparse
import os
import shutil
import stat
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE_DIRS = ("latest", "runs", "reports", "tmp")
KEEP_FILES = {".gitkeep"}


def _on_rm_error(func, path, exc_info):
    try:
        os.chmod(path, stat.S_IWRITE)
    except Exception:
        pass
    func(path)


def safe_remove(path: Path):
    if not path.exists():
        return
    if path.is_file() or path.is_symlink():
        try:
            os.chmod(path, stat.S_IWRITE)
        except Exception:
            pass
        path.unlink(missing_ok=True)
        return
    shutil.rmtree(path, onerror=_on_rm_error)


def ensure_base_layout(output_root: Path):
    output_root.mkdir(parents=True, exist_ok=True)
    for name in BASE_DIRS:
        (output_root / name).mkdir(parents=True, exist_ok=True)
    gitkeep = output_root / ".gitkeep"
    if not gitkeep.exists():
        gitkeep.write_text("", encoding="utf-8")


def clean_default(output_root: Path):
    keep = {"latest", "reports"}
    if not output_root.exists():
        ensure_base_layout(output_root)
        return

    for p in output_root.iterdir():
        if p.name in keep or p.name in KEEP_FILES:
            continue
        safe_remove(p)


def clean_nuke(output_root: Path):
    safe_remove(output_root)
    ensure_base_layout(output_root)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", default="output")
    parser.add_argument("--nuke", action="store_true")
    args = parser.parse_args()

    output_root = (ROOT / args.output_root).resolve()
    if args.nuke:
        clean_nuke(output_root)
        print(f"OK: nuked and rebuilt {output_root}")
        return

    clean_default(output_root)
    ensure_base_layout(output_root)
    print(f"OK: cleaned {output_root} (kept latest/ and reports/)")


if __name__ == "__main__":
    main()
