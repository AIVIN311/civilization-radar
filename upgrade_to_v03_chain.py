import sqlite3
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.settings import add_common_args, from_args

def table_or_view_exists(cur, name: str) -> bool:
    row = cur.execute(
        "SELECT 1 FROM sqlite_master WHERE (type='table' OR type='view') AND name=? LIMIT 1",
        (name,),
    ).fetchone()
    return bool(row)

def main():
    parser = argparse.ArgumentParser()
    add_common_args(parser)
    args = parser.parse_args()
    cfg = from_args(args)

    con = sqlite3.connect(cfg["db_path"])
    cur = con.cursor()

    # ensure tables exist by running builder at least once
    cur.execute("DROP VIEW IF EXISTS v03_chain_edges_latest")
    cur.execute("DROP VIEW IF EXISTS v03_series_chain_latest")

    if table_or_view_exists(cur, "chain_edges_decay_latest"):
        cur.execute("""
        CREATE VIEW v03_chain_edges_latest AS
          SELECT *
          FROM chain_edges_decay_latest;
        """)
    else:
        cur.execute("""
        CREATE VIEW v03_chain_edges_latest AS
          SELECT *
          FROM chain_edges_v10
          WHERE ts = (SELECT MAX(ts) FROM chain_edges_v10);
        """)

    if table_or_view_exists(cur, "series_chain_decay_latest"):
        cur.execute("""
        CREATE VIEW v03_series_chain_latest AS
          SELECT *
          FROM series_chain_decay_latest;
        """)
    else:
        cur.execute("""
        CREATE VIEW v03_series_chain_latest AS
          SELECT *
          FROM series_chain_v10
          WHERE ts = (SELECT MAX(ts) FROM series_chain_v10);
        """)
    con.commit()
    con.close()
    print("OK: created v03_chain_edges_latest + v03_series_chain_latest")

if __name__ == "__main__":
    main()
