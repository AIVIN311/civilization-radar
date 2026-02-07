# scripts/derive_events_from_daily.py
# Derive "events" from REAL daily snapshots (jsonl).
#
# It auto-detects the request field among:
#   dns_total, req, requests (with safe per-row fallback)
#
# Output: output/events_derived.jsonl

import json
import sys
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.event_strength import event_strength

INPUT = Path("output/daily_snapshots.jsonl")
OUTPUT = Path("output/events_derived.jsonl")

WINDOW = 3          # baseline days (excluding latest)
SPIKE_RATIO = 1.0   # event threshold using ratio: (latest - baseline_avg) / max(baseline_avg,1)
# Example: 1.0 => latest is ~2x baseline_avg triggers event


def load_rows(path: Path):
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def pick_req_key(rows) -> str:
    # Prefer common fields seen in snapshots
    candidates = ["dns_total", "req", "requests"]
    for k in candidates:
        for row in rows:
            v = row.get(k)
            if isinstance(v, (int, float)) or (isinstance(v, str) and v.isdigit()):
                return k
    return "dns_total"


def req_value(row: dict, req_key: str) -> int:
    v = row.get(req_key)
    if v is None:
        for k in ("dns_total", "req", "requests"):
            if k == req_key:
                continue
            v = row.get(k)
            if v is not None:
                break
    return to_int(v)


def to_int(v):
    try:
        return int(v or 0)
    except Exception:
        return 0


def main():
    if not INPUT.exists():
        raise SystemExit(f"❌ missing input: {INPUT}")

    rows = load_rows(INPUT)
    if not rows:
        raise SystemExit("❌ input is empty")

    req_key = pick_req_key(rows)

    by_domain = defaultdict(list)
    for r in rows:
        dom = r.get("domain")
        d = r.get("date")
        if not isinstance(dom, str) or not isinstance(d, str):
            continue
        by_domain[dom].append(r)

    events = []

    for domain, items in by_domain.items():
        # sort by date string (YYYY-MM-DD) works lexicographically
        items = sorted(items, key=lambda x: x.get("date", ""))

        if len(items) <= WINDOW:
            continue

        baseline_vals = [req_value(x, req_key) for x in items[:-1]]
        latest_val = req_value(items[-1], req_key)

        # baseline excludes latest day; use last WINDOW days if longer
        if len(baseline_vals) > WINDOW:
            baseline_vals = baseline_vals[-WINDOW:]

        baseline_avg = sum(baseline_vals) / max(1, len(baseline_vals))
        delta = latest_val - baseline_avg
        ratio = delta / max(baseline_avg, 1.0)

        # basic spike rule
        if ratio >= SPIKE_RATIO and latest_val >= 10:
            series_raw = items[-1].get("series")
            if not isinstance(series_raw, str) or not series_raw.strip():
                series_raw = "unmapped"
            series = series_raw
            origin_served = to_int(items[-1].get("origin_served"))
            cf_served = to_int(items[-1].get("cf_served"))

            events.append({
                "date": items[-1]["date"],
                "domain": domain,
                "series": series,
                "series_raw": series_raw,
                "type": "spike",
                "req_key": req_key,
                "baseline_avg": round(baseline_avg, 2),
                "current": latest_val,
                "delta": round(delta, 2),
                "ratio": round(ratio, 2),
                # optionally attach origin/cf ratios if available
                "origin_served": origin_served,
                "cf_served": cf_served,
                "strength": round(event_strength(baseline_avg, latest_val, origin_served, cf_served), 3),
            })

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8") as f:
        for e in events:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")

    print(f"✅ using req_key: {req_key}")
    print(f"✅ derived events written: {OUTPUT}")
    print(f"✅ events count: {len(events)}")


if __name__ == "__main__":
    main()
