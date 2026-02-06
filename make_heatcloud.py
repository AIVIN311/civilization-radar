# make_heatcloud.py
# Read output/daily_snapshots.jsonl, aggregate by series_map.json, and render:
# 1) pressure_heatcloud.png (文明壓力熱區雲)
# 2) pulse_compare.png (全域 vs Top series 脈衝對比)
# Also:
# 3) unmapped_domains.txt (未映射網域清單，結構洞)

import os
import json
import argparse
import math
from collections import defaultdict
from datetime import datetime, timedelta

import matplotlib.pyplot as plt
import matplotlib as mpl
mpl.rcParams["font.sans-serif"] = ["Microsoft JhengHei", "SimHei", "Noto Sans CJK TC", "Arial Unicode MS", "DejaVu Sans"]
mpl.rcParams["axes.unicode_minus"] = False
from matplotlib.ticker import FuncFormatter


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


def size_scale(score, max_score, mode="sqrt"):
    """
    Bubble size scaling for better "pressure terrain" readability.
    mode:
      - sqrt: default, good general
      - log : log on raw score (VERY effective for lifting small signals)
    """
    if max_score <= 0:
        return 30

    score = max(0.0, float(score))
    max_score = max(1.0, float(max_score))

    if mode == "log":
        # ✅ key: log on score, not on normalized ratio
        # This lifts small signals substantially.
        x = math.log1p(score) / math.log1p(max_score)
        x = clamp(x, 0.0, 1.0)
        return 30 + 970 * x

    # default sqrt (on normalized)
    x = score / max_score
    x = clamp(x, 0.0, 1.0)
    return 30 + 970 * math.sqrt(x)


def fmt_k(x, _):
    """Format large numbers as 1.2k / 3.4M for axis."""
    x = float(x)
    ax = abs(x)
    if ax >= 1_000_000:
        return f"{x/1_000_000:.1f}M"
    if ax >= 1_000:
        return f"{x/1_000:.1f}k"
    return f"{int(x)}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default="output/daily_snapshots.jsonl", help="input jsonl")
    ap.add_argument("--series-map", default="config/series_map.json", help="domain->series map json")
    ap.add_argument("--outdir", default="output", help="output directory")
    ap.add_argument("--days", type=int, default=7, help="how many days to aggregate for heatcloud")
    ap.add_argument("--top", type=int, default=25, help="how many top domains to label")
    ap.add_argument("--size-mode", choices=["sqrt", "log"], default="sqrt", help="bubble size scaling")
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
    # score = dns_total * (1 + origin_ratio) * (0.7 + (1 - cache_ratio))
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

    # ---- unmapped output (structure hole list) & exclude from heatcloud
    unmapped = [t for t in scored if t[2] == "unmapped"]
    if unmapped:
        out_unmapped = os.path.join(args.outdir, "unmapped_domains.txt")
        with open(out_unmapped, "w", encoding="utf-8") as f:
            f.write(f"# unmapped domains (end={end.isoformat()}, window={args.days}d)\n")
            for (score, dom, series, dns_total, origin_ratio, cache_ratio) in unmapped:
                f.write(
                    f"{dom}\tscore={score:.2f}\treq={dns_total}"
                    f"\torigin%={origin_ratio:.2f}\tcache%={cache_ratio:.2f}\n"
                )
        print(f"✅ Wrote: {out_unmapped} (count={len(unmapped)})")

    scored_plot = [t for t in scored if t[2] != "unmapped"]

    # ---- Figure 1: 文明壓力熱區雲 (scatter cloud)
    if not scored_plot:
        raise SystemExit("No mapped domains to plot (all unmapped).")

    series_list = sorted({s for _, _, s, *_ in scored_plot})
    y_index = {s: i for i, s in enumerate(series_list)}

    xs, ys, sizes = [], [], []

    max_score = max(s[0] for s in scored_plot) or 1.0

    for (score, dom, series, dns_total, origin_ratio, cache_ratio) in scored_plot:
        xs.append(score)
        ys.append(y_index[series])
        sizes.append(size_scale(score, max_score, mode=args.size_mode))

    plt.figure(figsize=(14, 8))
    plt.scatter(xs, ys, s=sizes, alpha=0.6)

    plt.yticks(range(len(series_list)), series_list)
    plt.xlabel(f"Pressure score (aggregate {args.days}d, end={end.isoformat()})")
    plt.title("文明壓力熱區雲 (Civilization Pressure Heatcloud)")

    # Log scale for x-axis (visual improvement only)
    plt.xscale("log")
    plt.gca().xaxis.set_major_formatter(FuncFormatter(fmt_k))

    # annotate:
    # 1) global top N
    top_global = scored_plot[: args.top]

    # 2) ensure at least 1 label per series (best in series)
    best_per_series = {}
    for t in scored_plot:
        s = t[2]
        if s not in best_per_series:
            best_per_series[s] = t

    # merge picks (avoid duplicates)
    pick = {t[1]: t for t in top_global}  # keyed by dom
    for t in best_per_series.values():
        pick.setdefault(t[1], t)

    # small deterministic jitter to reduce overlap
    for j, (score, dom, series, dns_total, origin_ratio, cache_ratio) in enumerate(pick.values()):
        y = y_index[series]
        dy = ((j % 5) - 2) * 0.06  # -0.12 ~ +0.12
        txt = f"{dom}\nreq={dns_total}  origin%={origin_ratio:.2f}"
        plt.text(score, y + 0.12 + dy, txt, fontsize=8)

    out1 = os.path.join(args.outdir, "pressure_heatcloud.png")
    plt.tight_layout()
    plt.savefig(out1, dpi=180)
    plt.close()

    # ---- Figure 2: pulse compare (global vs top series)
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
    print("✅ Done.")


if __name__ == "__main__":
    main()
