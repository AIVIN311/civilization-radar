import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.series_registry import resolve_series
from src.settings import add_common_args, from_args


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


def derive_event_level(cur, domain: str, date_text: str, fallback: str) -> str:
    row = cur.execute(
        """
        SELECT level_max
        FROM metrics_v02
        WHERE domain=? AND substr(ts,1,10)=?
        ORDER BY ts DESC
        LIMIT 1
        """,
        (domain, date_text),
    ).fetchone()
    if row and row[0]:
        return str(row[0])
    return fallback or "L1"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        default=None,
        help="Input events jsonl (default: <output-dir>/events_derived.jsonl)",
    )
    add_common_args(parser)
    args = parser.parse_args()
    cfg = from_args(args)

    in_path = Path(args.input) if args.input else Path(cfg["output_dir"]) / "events_derived.jsonl"
    if not in_path.exists():
        raise SystemExit(f"missing input: {in_path}")

    con = sqlite3.connect(cfg["db_path"])
    cur = con.cursor()
    if not table_exists(cur, "events_v01"):
        raise SystemExit("table events_v01 not found. Run: python scripts/apply_sql_migrations.py")

    cols = {r[1] for r in cur.execute("PRAGMA table_info(events_v01)").fetchall()}
    required = {"strength", "series_raw", "event_level", "matched_signals_json", "strength_explain_json"}
    if not required.issubset(cols):
        raise SystemExit(
            "events_v01 missing v0.4 columns. Run: python scripts/apply_sql_migrations.py"
        )

    n = 0
    with in_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            ev = json.loads(line)

            date = str(ev.get("date") or datetime.now(timezone.utc).strftime("%Y-%m-%d"))
            domain = str(ev.get("domain") or "").strip().lower()
            if not domain:
                continue
            event_type = str(ev.get("type") or "unknown")
            req_key = str(ev.get("req_key") or "dns_total")
            baseline_avg = to_float(ev.get("baseline_avg"), 0.0)
            current = to_float(ev.get("current"), 0.0)
            delta = to_float(ev.get("delta"), current - baseline_avg)
            ratio = to_float(ev.get("ratio"), (current / baseline_avg if baseline_avg else 0.0))
            strength = to_float(ev.get("strength"), 0.0)
            origin_served = ev.get("origin_served")
            cf_served = ev.get("cf_served")
            series_raw = str(ev.get("series_raw") or ev.get("series") or "unmapped")
            series = resolve_series(series_raw, domain)
            ts = str(ev.get("ts") or (date + "T00:00:00Z"))
            fallback_level = str(ev.get("event_level") or "L1")
            event_level = derive_event_level(cur, domain, date, fallback_level)
            matched_signals = ev.get("matched_signals") or []
            explain = ev.get("strength_explain") or {}

            cur.execute(
                """
                INSERT INTO events_v01
                (ts, date, domain, series, event_type, req_key, baseline_avg, current, delta, ratio,
                 origin_served, cf_served, strength, series_raw,
                 event_level, matched_signals_json, strength_explain_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                  series_raw=excluded.series_raw,
                  event_level=excluded.event_level,
                  matched_signals_json=excluded.matched_signals_json,
                  strength_explain_json=excluded.strength_explain_json
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
                    event_level,
                    json.dumps(matched_signals, ensure_ascii=False),
                    json.dumps(explain, ensure_ascii=False),
                ),
            )
            n += cur.rowcount

    con.commit()
    con.close()
    print(f"inserted events: {n}")


if __name__ == "__main__":
    main()
