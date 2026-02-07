import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.event_strength import event_strength_explain
from src.series_registry import resolve_series
from src.settings import add_common_args, from_args


WINDOW = 3
SPIKE_RATIO = 1.0


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
    candidates = ["dns_total", "req", "requests"]
    for k in candidates:
        for row in rows:
            v = row.get(k)
            if isinstance(v, (int, float)) or (isinstance(v, str) and v.isdigit()):
                return k
    return "dns_total"


def to_int(v):
    try:
        return int(v or 0)
    except Exception:
        return 0


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


def matched_signals(row: dict) -> list[str]:
    signals = []
    sig = str(row.get("sig") or "").strip()
    if sig:
        signals.append(sig)
    notes = str(row.get("notes") or "").lower()
    if "/.env" in notes:
        signals.append("env_secret")
    if "/wp-login.php" in notes:
        signals.append("wp_probe")
    return sorted(set(signals))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        default=None,
        help="Input daily snapshots jsonl (default: <output-dir>/daily_snapshots.jsonl)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output events jsonl (default: <output-dir>/events_derived.jsonl)",
    )
    add_common_args(parser)
    args = parser.parse_args()
    cfg = from_args(args)

    input_path = Path(args.input) if args.input else Path(cfg["output_dir"]) / "daily_snapshots.jsonl"
    output_path = Path(args.output) if args.output else Path(cfg["output_dir"]) / "events_derived.jsonl"

    if not input_path.exists():
        raise SystemExit(f"missing input: {input_path}")

    rows = load_rows(input_path)
    if not rows:
        raise SystemExit("input is empty")

    req_key = pick_req_key(rows)
    by_domain = defaultdict(list)
    for r in rows:
        dom = r.get("domain")
        d = r.get("date")
        if not isinstance(dom, str) or not dom.strip():
            continue
        if not isinstance(d, str) or not d.strip():
            ts = str(r.get("ts") or "")
            if len(ts) >= 10:
                d = ts[:10]
            else:
                continue
        by_domain[dom.strip().lower()].append({**r, "date": d})

    events = []
    for domain, items in by_domain.items():
        items = sorted(items, key=lambda x: x.get("date", ""))
        if len(items) <= WINDOW:
            continue
        baseline_vals = [req_value(x, req_key) for x in items[:-1]]
        latest_val = req_value(items[-1], req_key)
        if len(baseline_vals) > WINDOW:
            baseline_vals = baseline_vals[-WINDOW:]
        baseline_avg = sum(baseline_vals) / max(1, len(baseline_vals))
        delta = latest_val - baseline_avg
        ratio = delta / max(baseline_avg, 1.0)

        if ratio >= SPIKE_RATIO and latest_val >= 10:
            latest = items[-1]
            origin_served = to_int(latest.get("origin_served"))
            cf_served = to_int(latest.get("cf_served"))
            series_raw = str(latest.get("series") or latest.get("series_raw") or "unmapped")
            series = resolve_series(series_raw, domain)
            explain = event_strength_explain(
                baseline_avg=baseline_avg,
                current=latest_val,
                origin_served=origin_served,
                cf_served=cf_served,
            )
            level = "L1"
            sig = str(latest.get("sig") or "").lower()
            note = str(latest.get("notes") or "").lower()
            if "env_scan" in sig or "/.env" in note:
                level = "L3"
            elif sig in ("wp_scan", "config_scan"):
                level = "L2"

            events.append(
                {
                    "date": latest["date"],
                    "domain": domain,
                    "series": series,
                    "series_raw": series_raw,
                    "type": "spike",
                    "req_key": req_key,
                    "baseline_avg": round(baseline_avg, 4),
                    "current": latest_val,
                    "delta": round(delta, 4),
                    "ratio": round(ratio, 4),
                    "origin_served": origin_served,
                    "cf_served": cf_served,
                    "strength": float(explain["strength_final"]),
                    "event_level": level,
                    "matched_signals": matched_signals(latest),
                    "strength_explain": explain,
                    "ts": str(latest.get("ts") or f"{latest['date']}T00:00:00Z"),
                }
            )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        for e in events:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")

    print(f"using req_key: {req_key}")
    print(f"derived events written: {output_path}")
    print(f"events count: {len(events)}")


if __name__ == "__main__":
    main()
