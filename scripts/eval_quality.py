import argparse
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.settings import add_common_args, from_args


def fetch_one(cur, sql, params=()):
    return cur.execute(sql, params).fetchone()[0]


def check_ts_out_of_order(cur):
    row = cur.execute(
        """
        WITH ordered AS (
          SELECT domain, ts, id,
                 LAG(ts) OVER (PARTITION BY domain ORDER BY id) AS prev_ts
          FROM snapshots_v01
        )
        SELECT COUNT(*)
        FROM ordered
        WHERE prev_ts IS NOT NULL AND ts < prev_ts
        """
    ).fetchone()
    return int(row[0] if row else 0)


def build_report(cur, missing_ratio_threshold: float):
    checks = {}
    checks["events_empty"] = int(fetch_one(cur, "SELECT COUNT(*)=0 FROM events_v01"))
    checks["edges_empty"] = int(fetch_one(cur, "SELECT COUNT(*)=0 FROM v03_chain_edges_latest"))
    checks["metrics_null"] = int(
        fetch_one(
            cur,
            """
            SELECT COUNT(*) FROM metrics_v02
            WHERE ts IS NULL OR ts='' OR W IS NULL OR A IS NULL OR D IS NULL OR Hstar IS NULL
               OR W!=W OR A!=A OR D!=D OR Hstar!=Hstar
               OR ABS(W) > 1e308 OR ABS(A) > 1e308 OR ABS(D) > 1e308 OR ABS(Hstar) > 1e308
            """,
        )
    )
    checks["series_chain_null"] = int(
        fetch_one(
            cur,
            """
            SELECT COUNT(*) FROM v03_series_chain_latest
            WHERE series IS NULL OR series='' OR W_avg IS NULL OR W_proj IS NULL
            """,
        )
    )
    checks["dup_metrics_pk"] = int(
        fetch_one(
            cur,
            "SELECT COUNT(*) FROM (SELECT ts,domain,COUNT(*) c FROM metrics_v02 GROUP BY ts,domain HAVING c>1)",
        )
    )
    checks["dup_events_key"] = int(
        fetch_one(
            cur,
            "SELECT COUNT(*) FROM (SELECT date,domain,event_type,req_key,COUNT(*) c FROM events_v01 GROUP BY date,domain,event_type,req_key HAVING c>1)",
        )
    )
    checks["missing_ts"] = int(
        fetch_one(cur, "SELECT COUNT(*) FROM snapshots_v01 WHERE ts IS NULL OR ts=''")
    )
    checks["ts_out_of_order"] = int(check_ts_out_of_order(cur))
    total = int(fetch_one(cur, "SELECT COUNT(*) FROM snapshots_v01"))
    missing_rows = int(
        fetch_one(
            cur,
            """
            SELECT COUNT(*) FROM snapshots_v01
            WHERE COALESCE(missing_fields_json,'[]') NOT IN ('[]','')
            """,
        )
    )
    ratio = (missing_rows / total) if total else 0.0
    checks["missing_fields_rows"] = missing_rows
    checks["missing_fields_ratio"] = ratio
    checks["missing_fields_ratio_abnormal"] = int(ratio > missing_ratio_threshold)
    return checks


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--missing-ratio-threshold", type=float, default=0.0)
    add_common_args(parser)
    args = parser.parse_args()
    cfg = from_args(args)

    con = sqlite3.connect(cfg["db_path"])
    cur = con.cursor()
    report = build_report(cur, args.missing_ratio_threshold)
    con.close()

    critical = [
        "events_empty",
        "edges_empty",
        "metrics_null",
        "series_chain_null",
        "dup_metrics_pk",
        "dup_events_key",
        "missing_ts",
        "ts_out_of_order",
        "missing_fields_ratio_abnormal",
    ]
    failed = [k for k in critical if report.get(k, 0) > 0]
    report["critical_failed"] = failed
    report["ok"] = len(failed) == 0
    report["db_path"] = cfg["db_path"]

    Path(cfg["report_dir"]).mkdir(parents=True, exist_ok=True)
    out_path = Path(cfg["report_dir"]) / "eval_quality.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("=== Quality Gate v0.4 ===")
    for k in critical:
        print(f"{k}: {report.get(k)}")
    print(f"report: {out_path}")

    if failed:
        print("FAILED:", ", ".join(failed))
        raise SystemExit(1)
    print("PASS")


if __name__ == "__main__":
    main()
