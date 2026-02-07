import sqlite3
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.settings import add_common_args, from_args

SQL_FILES = [
    "scripts/sql/events_v01.sql",
    "scripts/sql/views_events_series.sql",
    "scripts/sql/views_series_w_timeseries.sql",
    "scripts/sql/views_chain_push.sql",
    "scripts/sql/views_chain_from_events.sql",
    "scripts/sql/views_v03_series_chain_latest.sql",
]

EVENTS_V04_COLUMNS = [
    ("strength", "REAL"),
    ("series_raw", "TEXT"),
    ("event_level", "TEXT DEFAULT 'L1'"),
    ("matched_signals_json", "TEXT DEFAULT '[]'"),
    ("strength_explain_json", "TEXT DEFAULT '{}'")
]

CHAIN_GEO_COLUMNS = [
    ("geo_profile", "TEXT NOT NULL DEFAULT 'tw'"),
    ("geo_factor", "REAL NOT NULL DEFAULT 0.0"),
    ("geo_factor_explain_json", "TEXT NOT NULL DEFAULT '{}'"),
    ("tw_rank_score", "REAL NOT NULL DEFAULT 0.0"),
    ("tw_rank_explain_json", "TEXT NOT NULL DEFAULT '{}'"),
]

def read_sql(path: str) -> str:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Missing SQL file: {path}")
    return p.read_text(encoding="utf-8")


def table_exists(cur, table_name: str) -> bool:
    row = cur.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
        (table_name,),
    ).fetchone()
    return bool(row)


def table_columns(cur, table_name: str) -> set[str]:
    return {r[1] for r in cur.execute(f"PRAGMA table_info({table_name})").fetchall()}


def ensure_table_columns(cur, table_name: str, columns: list[tuple[str, str]]):
    if not table_exists(cur, table_name):
        return
    cols = table_columns(cur, table_name)
    for col, decl in columns:
        if col in cols:
            print(f"INFO: column {col} already exists, skipping")
            continue
        cur.execute(f"ALTER TABLE {table_name} ADD COLUMN {col} {decl}")
        cols.add(col)


def ensure_events_v04_columns(cur):
    ensure_table_columns(cur, "events_v01", EVENTS_V04_COLUMNS)


def ensure_chain_geo_columns(cur):
    ensure_table_columns(cur, "series_chain_v10", CHAIN_GEO_COLUMNS)
    ensure_table_columns(cur, "series_chain_decay_latest", CHAIN_GEO_COLUMNS)

def main():
    parser = argparse.ArgumentParser()
    add_common_args(parser)
    args = parser.parse_args()
    cfg = from_args(args)

    con = sqlite3.connect(cfg["db_path"])
    cur = con.cursor()

    # Make sure foreign keys on (harmless even if unused)
    cur.execute("PRAGMA foreign_keys=ON;")

    for f in SQL_FILES:
        sql = read_sql(f)
        try:
            con.executescript(sql)
            print(f"✅ applied: {f}")
        except Exception as e:
            print(f"❌ failed: {f}\n{e}")
            raise

    ensure_events_v04_columns(cur)
    ensure_chain_geo_columns(cur)
    con.commit()

    # quick verify
    tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()]
    views  = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='view' ORDER BY name").fetchall()]
    print(f"tables: {len(tables)}  views: {len(views)}")
    print("tables sample:", tables[:15])
    print("views  sample:", views[:15])

    con.close()

if __name__ == "__main__":
    main()
