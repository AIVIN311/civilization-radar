import json
import math
from collections import defaultdict


INPUT_PATH = "output/event_maps.jsonl"
OUTPUT_PATH = "event_forcing_v0.2.json"

TAU = 12.0
LAMBDA_EVENT = 0.20


def slot_of_ts(ts: str) -> str:
    # Placeholder: hourly bucket (YYYY-MM-DDTHH)
    return (ts or "")[:13]


def load_event_maps(path: str):
    events = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return events


def build_raw(events):
    # E_raw[slot][series] = max(scaled_energy)
    raw = defaultdict(dict)
    for ev in events:
        ts = ev.get("ts") or ev.get("timestamp") or ""
        slot = slot_of_ts(ts)
        if not slot:
            continue
        for m in ev.get("maps", []) or []:
            series = m.get("series")
            if not series:
                continue
            try:
                energy = float(m.get("energy", 0.0))
            except (TypeError, ValueError):
                energy = 0.0
            scaled = energy * LAMBDA_EVENT
            prev = raw[slot].get(series, 0.0)
            if scaled > prev:
                raw[slot][series] = scaled
    return raw


def build_decay(raw):
    # E_decay[slot][series] = E_raw + exp(-1/tau) * prev_decay
    decay = defaultdict(dict)
    slots = sorted(raw.keys())
    if not slots:
        return decay, slots

    decay_factor = math.exp(-1.0 / TAU)
    prev = defaultdict(float)

    for slot in slots:
        current = {}
        # carry over all previous series with decay
        for series, prev_val in prev.items():
            if prev_val <= 0:
                continue
            current[series] = prev_val * decay_factor
        # add current raw
        for series, raw_val in raw.get(slot, {}).items():
            current[series] = current.get(series, 0.0) + raw_val
        # persist
        for series, val in current.items():
            if val > 0:
                decay[slot][series] = val
        prev = defaultdict(float, current)

    return decay, slots


def main():
    events = load_event_maps(INPUT_PATH)
    raw = build_raw(events)
    decay, slots = build_decay(raw)

    out = {
        "meta": {
            "tau": TAU,
            "lambda_event": LAMBDA_EVENT,
            "slotting": "slot_of_ts(ts) -> ts[:13] (hourly bucket placeholder)",
        },
        "E_raw": raw,
        "E_decay": decay,
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    latest_slot = slots[-1] if slots else None
    latest_forcing = decay.get(latest_slot, {}) if latest_slot else {}
    top5 = sorted(latest_forcing.items(), key=lambda x: x[1], reverse=True)[:5]

    print(f"slots: {len(slots)}")
    if latest_slot:
        print(f"latest_slot: {latest_slot}")
    if top5:
        print("top5_series_latest_forcing:")
        for series, val in top5:
            print(f"  {series}: {val:.6f}")
    else:
        print("top5_series_latest_forcing: (none)")
    print(f"output: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
