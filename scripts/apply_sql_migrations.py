import sqlite3
from pathlib import Path

DB_PATH = "radar.db"
SQL_FILES = [
    "scripts/sql/events_v01.sql",
    "scripts/sql/views_events_series.sql",
    "scripts/sql/views_series_w_timeseries.sql",
    "scripts/sql/views_chain_push.sql",
    "scripts/sql/views_chain_from_events.sql",
    "scripts/sql/views_v03_series_chain_latest.sql",
]

def read_sql(path: str) -> str:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Missing SQL file: {path}")
    return p.read_text(encoding="utf-8")

def main():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    # Make sure foreign keys on (harmless even if unused)
    cur.execute("PRAGMA foreign_keys=ON;")

    for f in SQL_FILES:
        sql = read_sql(f)
        try:
            con.executescript(sql)
            print(f"✅ applied: {f}")
        except sqlite3.OperationalError as e:
            msg = str(e).lower()
            if "duplicate column name" in msg:
                print(f"⚠️ duplicate column ignored: {f} ({e})")
                continue
            print(f"❌ failed: {f}\n{e}")
            raise
        except Exception as e:
            print(f"❌ failed: {f}\n{e}")
            raise

    con.commit()

    # quick verify
    tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()]
    views  = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='view' ORDER BY name").fetchall()]
    print(f"✅ tables: {len(tables)}  views: {len(views)}")
    print("tables sample:", tables[:15])
    print("views  sample:", views[:15])

    con.close()

if __name__ == "__main__":
    main()
