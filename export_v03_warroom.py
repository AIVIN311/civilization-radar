# export_v03_warroom.py
# Build v0.3 warroom JSON from REAL daily snapshots + series map.
#
# Output:
#   output/v03_warroom.json
#
# Usage:
#   python export_v03_warroom.py --days 7 --spark-slots 16

import os, json, argparse, math
from datetime import datetime, timedelta
from collections import defaultdict

def load_jsonl(path):
    rows = []
    if not os.path.exists(path):
        return rows
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    return rows

def load_json(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def parse_date(s):
    return datetime.strptime(s, "%Y-%m-%d").date()

def clamp(x, lo, hi):
    return max(lo, min(hi, x))

def safe_div(a, b):
    return a / b if b else 0.0

def robust_z(values, x):
    # robust z-score using median/MAD
    vs = sorted(values)
    if not vs:
        return 0.0
    n = len(vs)
    med = vs[n//2] if n % 2 == 1 else 0.5*(vs[n//2-1]+vs[n//2])
    absdev = [abs(v - med) for v in vs]
    absdev.sort()
    mad = absdev[n//2] if n % 2 == 1 else 0.5*(absdev[n//2-1]+absdev[n//2])
    if mad == 0:
        return 0.0
    # 1.4826 makes MAD comparable to std for normal dist
    return (x - med) / (1.4826 * mad)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snap", default="output/daily_snapshots.jsonl")
    ap.add_argument("--series-map", default="config/series_map.json")
    ap.add_argument("--out", default="output/v03_warroom.json")
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--spark-slots", type=int, default=16)
    args = ap.parse_args()

    rows = load_jsonl(args.snap)
    smap = load_json(args.series_map, default={}) or {}
    smap = {str(k).lower(): str(v) for k, v in smap.items()}

    # collect available dates
    dates = [parse_date(r["date"]) for r in rows if isinstance(r.get("date"), str)]
    if not dates:
        raise SystemExit("No valid dates in daily_snapshots.jsonl")

    end = max(dates)
    start = end - timedelta(days=args.days - 1)

    # build per-domain daily series within window (for sparkline)
    dom_day = defaultdict(lambda: defaultdict(int))  # dom -> date -> dns_total
    dom_series = {}
    dom_origin = defaultdict(lambda: defaultdict(int))  # dom -> date -> origin_served
    dom_cf = defaultdict(lambda: defaultdict(int))      # dom -> date -> cf_served

    for r in rows:
        d = r.get("date")
        dom = r.get("domain")
        if not isinstance(d, str) or not isinstance(dom, str):
            continue
        dd = parse_date(d)
        if dd < start or dd > end:
            continue
        dom_l = dom.lower()
        dns_total = int(r.get("dns_total") or 0)
        dom_day[dom_l][dd] += dns_total
        dom_origin[dom_l][dd] += int(r.get("origin_served") or 0)
        dom_cf[dom_l][dd] += int(r.get("cf_served") or 0)
        dom_series[dom_l] = smap.get(dom_l, "unmapped")

    # create axis days (spark slots may be > days; we compress)
    days_axis = [start + timedelta(days=i) for i in range(args.days)]
    # compress to spark-slots by sampling/aggregating
    slots = args.spark_slots
    if slots <= 1:
        slots = 1
    # map day index -> slot index
    def day_to_slot(i):
        return int((i / max(1, args.days - 1)) * (slots - 1))

    # Build per-domain sparkline values (slot sums)
    dom_spark = {}
    dom_sum = {}
    dom_last = {}
    for dom, mp in dom_day.items():
        arr = [0] * slots
        for i, dd in enumerate(days_axis):
            v = mp.get(dd, 0)
            si = day_to_slot(i)
            arr[si] += v
        dom_spark[dom] = arr
        dom_sum[dom] = sum(arr)
        dom_last[dom] = arr[-1] if arr else 0

    # Compute A (anomaly score) per domain using robust z of last slot vs its own history
    # A is "how weird is the latest" (self-baseline)
    dom_A = {}
    for dom, arr in dom_spark.items():
        if len(arr) < 4:
            dom_A[dom] = 0.0
        else:
            hist = arr[:-1]  # baseline
            dom_A[dom] = robust_z(hist, arr[-1])

    # Compute W (weight/pressure) using log-scaled volume + origin ratio
    dom_W = {}
    dom_origin_ratio = {}
    for dom, arr in dom_spark.items():
        total = sum(arr)
        # origin ratio across window
        o = sum(dom_origin[dom].values())
        c = sum(dom_cf[dom].values())
        dns = max(1, total)
        origin_ratio = o / dns
        dom_origin_ratio[dom] = origin_ratio

        # W: emphasize volume but compress with log; boost if origin-heavy
        W = math.log10(1 + total) * (1.0 + 0.8 * origin_ratio)
        dom_W[dom] = W

    # Delta: last slot vs previous slot relative change
    dom_d = {}
    for dom, arr in dom_spark.items():
        if len(arr) < 2:
            dom_d[dom] = 0.0
        else:
            prev = arr[-2]
            cur = arr[-1]
            dom_d[dom] = safe_div(cur - prev, max(1, prev))

    # Level rules (match your UI semantics)
    # A < 1.0 background, >=1 suspicious, >=2 warning, >=3 event
    def level_of(A):
        if A >= 3.0:
            return "事件"
        if A >= 2.0:
            return "警戒"
        if A >= 1.0:
            return "可疑"
        return "背景"

    # L3 definition (you can tune): event-level and origin_ratio high
    def is_L3(A, origin_ratio):
        return (A >= 3.0) and (origin_ratio >= 0.6)

    # Build series aggregates for "系列戰情"
    series_dom = defaultdict(list)
    for dom, s in dom_series.items():
        series_dom[s].append(dom)

    series_stats = []
    for s, doms in series_dom.items():
        if s == "unmapped":
            continue
        totalW = sum(dom_W[d] for d in doms)
        avgW = safe_div(totalW, len(doms))
        # projected: simple heuristic -> recent acceleration proxy
        accel = sum(dom_d[d] for d in doms) / max(1, len(doms))
        W_proj = avgW * (1.0 + clamp(accel, -0.5, 1.0))
        series_stats.append({
            "series": s,
            "W_avg": round(avgW, 3),
            "W_proj": round(W_proj, 3),
            "domains": len(doms),
        })

    series_stats.sort(key=lambda x: x["W_proj"], reverse=True)

    # Domain rows for leaderboard
    dom_rows = []
    for dom in dom_spark.keys():
        A = dom_A[dom]
        W = dom_W[dom]
        d = dom_d[dom]
        s = dom_series.get(dom, "unmapped")
        origin_ratio = dom_origin_ratio.get(dom, 0.0)
        lv = level_of(A)
        l3 = is_L3(A, origin_ratio)
        dom_rows.append({
            "domain": dom,
            "series": s,
            "level": lv + (" L3" if l3 else ""),
            "A": round(A, 2),
            "W": round(W, 3),
            "delta": round(d, 3),
            "spark": dom_spark[dom],
            "origin_ratio": round(origin_ratio, 2),
            "sig": "real",   # placeholder for now (later we map from signals)
            "matched": [],   # later fill from event detector
        })

    dom_rows.sort(key=lambda x: (x["A"], x["W"]), reverse=True)

    payload = {
        "version": "0.3",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "window": {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "days": args.days,
            "spark_slots": args.spark_slots
        },
        "thresholds": {
            "background_lt": 1.0,
            "suspicious_ge": 1.0,
            "warning_ge": 2.0,
            "event_ge": 3.0
        },
        "domains": dom_rows,
        "series": series_stats
    }

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print("✅ Wrote:", args.out)
    print("✅ Domains:", len(dom_rows), " Series:", len(series_stats))
    print("✅ Window:", start.isoformat(), "~", end.isoformat())

if __name__ == "__main__":
    main()
