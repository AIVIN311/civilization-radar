import sys
from pathlib import Path

# ensure repo root is on sys.path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from src.series_canonical import resolve_series

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.series_resolver import resolve

DB_PATH = "radar.db"
IN_PATH = Path("output/events_derived.jsonl")


def table_exists(cur, name: str) -> bool:
    row = cur.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
        (name,),
    ).fetchone()
    return bool(row)


def to_float(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return float(default)


def main():
    if not IN_PATH.exists():
        raise SystemExit(f"❌ missing input: {IN_PATH}")

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    if not table_exists(cur, "events_v01"):
        raise SystemExit("❌ table events_v01 not found. Run: python scripts/apply_sql_migrations.py")

    cols = {r[1] for r in cur.execute("PRAGMA table_info(events_v01)").fetchall()}
    required = {"strength", "series_raw"}
    if not required.issubset(cols):
        raise SystemExit("❌ events_v01 missing columns strength/series_raw. Run: python scripts/apply_sql_migrations.py")

    n = 0
    with IN_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            ev = json.loads(line)

            date = ev.get("date")
            domain = ev.get("domain")
            event_type = ev.get("type") or "unknown"
            req_key = ev.get("req_key") or "dns_total"

            baseline_avg = to_float(ev.get("baseline_avg"), 0.0)
            current = to_float(ev.get("current"), 0.0)
            delta = to_float(ev.get("delta"), current - baseline_avg)
            ratio = to_float(ev.get("ratio"), (current / baseline_avg if baseline_avg else 0.0))
            strength = to_float(ev.get("strength"), 0.0)

            origin_served = ev.get("origin_served")
            cf_served = ev.get("cf_served")
            series_raw = ev.get("series_raw") or ev.get("series") or "unmapped"
            series = resolve(domain, series_raw)

            if not date:
                date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            ts = ev.get("ts") or (date + "T00:00:00Z")

            cur.execute(
                """
                INSERT INTO events_v01
                (ts, date, domain, series, event_type, req_key, baseline_avg, current, delta, ratio,
                 origin_served, cf_served, strength, series_raw)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(date, domain, event_type, req_key) DO UPDATE SET
                  ts=excluded.ts,
                  series=excluded.series,
                  baseline_avg=excluded.baseline_avg,
                  current=excluded.current,
                  delta=excluded.delta,
                  ratio=excluded.ratio,
                  origin_served=excluded.origin_served,
                  cf_served=excluded.cf_served,
                  strength=excluded.strength,
                  series_raw=excluded.series_raw
                """,
                (
                    ts,
                    date,
                    domain,
                    series,
                    event_type,
                    req_key,
                    baseline_avg,
                    current,
                    delta,
                    ratio,
                    origin_served,
                    cf_served,
                    strength,
                    series_raw,
                ),
            )
            n += cur.rowcount

    con.commit()
    con.close()
    print(f"✅ inserted events: {n}")


if __name__ == "__main__":
    main()
