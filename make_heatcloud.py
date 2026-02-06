# make_heatcloud.py
# Read output/daily_snapshots.jsonl, aggregate by series_map.json, and render:
# 1) pressure_heatcloud.png (文明壓力熱區雲)
# 2) pulse_compare.png (全域 vs Top series 脈衝對比)

import os
import json
import argparse
from collections import defaultdict
from datetime import datetime, timedelta

import matplotlib.pyplot as plt


def load_jsonl(path: str) -> list[dict]:
    rows = []
    if not os.path.exists(path):
        raise FileNotFoundError(f"jsonl not found: {path}")
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


def load_series_map(path: str) -> dict[str, str]:
    if not os.path.exists(path):
        raise FileNotFoundError(f"series_map.json not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        m = json.load(f)
    # normalize keys to lowercase
    out = {}
    for k, v in m.items():
        if isinstance(k, str) and isinstance(v, str):
            out[k.lower()] = v
    return out


def parse_date(s: str):
    # expects YYYY-MM-DD
    return datetime.strptime(s, "%Y-%m-%d").date()


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default="output/daily_snapshots.jsonl", help="input jsonl")
    ap.add_argument("--series-map", default="config/series_map.json", help="domain->series map json")
    ap.add_argument("--outdir", default="output", help="output directory")
    ap.add_argument("--days", type=int, default=7, help="how many days to aggregate for heatcloud")
    ap.add_argument("--top", type=int, default=25, help="how many top domains to label")
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)

    rows = load_jsonl(args.inp)
    smap = load_series_map(args.series_map)

    # filter window
    all_dates = [parse_date(r["date"]) for r in rows if isinstance(r.get("date"), str)]
    if not all_dates:
        raise SystemExit("No valid dates in input.")
    end = max(all_dates)
    start = end - timedelta(days=args.days - 1)

    window = []
    for r in rows:
        d = r.get("date")
        dom = r.get("domain")
        if not isinstance(d, str) or not isinstance(dom, str):
            continue
        dd = parse_date(d)
        if dd < start or dd > end:
            continue
        window.append(r)

    # domain stats (sum over window)
    dom_stat = defaultdict(lambda: {"dns_total": 0, "cf_served": 0, "origin_served": 0})
    for r in window:
        dom = r["domain"].lower()
        dom_stat[dom]["dns_total"] += int(r.get("dns_total") or 0)
        dom_stat[dom]["cf_served"] += int(r.get("cf_served") or 0)
        dom_stat[dom]["origin_served"] += int(r.get("origin_served") or 0)

    # pressure score:
    # - base = dns_total
    # - weight more if origin_served high (less cache / more "real hits" or more pressure on origin)
    # score = dns_total * (1 + origin_ratio)
    scored = []
    for dom, s in dom_stat.items():
        dns_total = s["dns_total"]
        origin = s["origin_served"]
        cf = s["cf_served"]
        denom = max(1, dns_total)
        origin_ratio = origin / denom
        cache_ratio = cf / denom
        score = dns_total * (1.0 + origin_ratio) * (0.7 + (1 - cache_ratio))  # mild boost to non-cache
        series = smap.get(dom, "unmapped")
        scored.append((score, dom, series, dns_total, origin_ratio, cache_ratio))

    scored.sort(reverse=True, key=lambda x: x[0])

    # ---- Figure 1: 文明壓力熱區雲 (scatter cloud)
    # y-axis = series buckets
    series_list = sorted({s for _, _, s, *_ in scored})
    y_index = {s: i for i, s in enumerate(series_list)}

    xs = []
    ys = []
    sizes = []
    labels = []

    # normalize bubble sizes
    if scored:
        max_score = max(s[0] for s in scored) or 1.0
    else:
        max_score = 1.0

    for i, (score, dom, series, dns_total, origin_ratio, cache_ratio) in enumerate(scored):
        xs.append(score)
        ys.append(y_index[series])
        # bubble size: scale with score
        sz = 30 + 970 * (score / max_score)
        sizes.append(sz)
        labels.append(dom)

    plt.figure(figsize=(14, 8))
    plt.scatter(xs, ys, s=sizes, alpha=0.6)
    plt.yticks(range(len(series_list)), series_list)
    plt.xlabel(f"Pressure score (aggregate {args.days}d, end={end.isoformat()})")
    plt.title("文明壓力熱區雲 (Civilization Pressure Heatcloud)")

    # annotate top N
    for (score, dom, series, dns_total, origin_ratio, cache_ratio) in scored[: args.top]:
        y = y_index[series]
        txt = f"{dom}\nreq={dns_total}  origin%={origin_ratio:.2f}"
        plt.text(score, y + 0.08, txt, fontsize=8)

    out1 = os.path.join(args.outdir, "pressure_heatcloud.png")
    plt.tight_layout()
    plt.savefig(out1, dpi=180)
    plt.close()

    # ---- Figure 2: pulse compare (global vs top series)
    # build daily totals for last max(args.days, 14) days to see rhythm
    pulse_days = max(args.days, 14)
    p_start = end - timedelta(days=pulse_days - 1)

    day_total = defaultdict(int)
    day_series = defaultdict(lambda: defaultdict(int))

    for r in rows:
        d = r.get("date")
        dom = r.get("domain")
        if not isinstance(d, str) or not isinstance(dom, str):
            continue
        dd = parse_date(d)
        if dd < p_start or dd > end:
            continue
        dns_total = int(r.get("dns_total") or 0)
        day_total[dd] += dns_total
        series = smap.get(dom.lower(), "unmapped")
        day_series[series][dd] += dns_total

    # pick top 3 series by total volume in the window
    series_sum = []
    for s, mp in day_series.items():
        series_sum.append((sum(mp.values()), s))
    series_sum.sort(reverse=True)
    top_series = [s for _, s in series_sum[:3]]

    days_axis = [p_start + timedelta(days=i) for i in range(pulse_days)]
    y_all = [day_total.get(d, 0) for d in days_axis]

    plt.figure(figsize=(14, 6))
    plt.plot(days_axis, y_all, linewidth=2, label="ALL")

    for s in top_series:
        ys2 = [day_series[s].get(d, 0) for d in days_axis]
        plt.plot(days_axis, ys2, linewidth=1.5, label=s)

    plt.title("Pulse Compare (全域 vs Top series)")
    plt.xlabel("Date")
    plt.ylabel("Requests (dns_total)")
    plt.xticks(rotation=35)
    plt.legend()
    plt.tight_layout()

    out2 = os.path.join(args.outdir, "pulse_compare.png")
    plt.savefig(out2, dpi=180)
    plt.close()

    print("✅ Generated:")
    print(f" - {out1}")
    print(f" - {out2}")
    print(f"✅ Window for heatcloud: {start.isoformat()} ~ {end.isoformat()} ({args.days} days)")
    print(f"✅ Top series in pulse: {top_series}")


if __name__ == "__main__":
    main()
