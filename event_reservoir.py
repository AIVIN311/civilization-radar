# event_reservoir.py
import json, math, os
from collections import defaultdict

TAU = 12  # same as your chain decay
LAMBDA_EVENT = 0.20  # event forcing strength (start conservative)

def slot_of_ts(ts: str) -> str:
    # v0: treat each event ts as its own slot key
    # if you already have slotting logic in your pipeline, replace this.
    return ts[:13]  # "YYYY-MM-DDTHH" hourly bucket

def decay_factor(delta_slots: int, tau: float=TAU) -> float:
    return math.exp(-delta_slots / tau)

def load_jsonl(path):
    out = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                out.append(json.loads(line))
    return out

def build_reservoir(event_maps_path: str):
    rows = load_jsonl(event_maps_path)

    # E_raw[slot][series] = max_energy_in_slot (merge duplicates)
    E_raw = defaultdict(lambda: defaultdict(float))

    for ev in rows:
        slot = slot_of_ts(ev["ts"])
        fp = ev.get("fingerprint")
        # you can use novelty here later; v0 just uses energy
        for m in ev.get("maps", []):
            s = m["series"]
            e = float(m.get("energy", 0.0)) * LAMBDA_EVENT  # scale here (noise control)
            if e > E_raw[slot][s]:
                E_raw[slot][s] = e

    return E_raw

def to_sorted_slots(E_raw):
    slots = sorted(E_raw.keys())
    return slots

def compute_decayed_series(E_raw):
    """
    Output:
      E_decay[slot][series] = sum_{past slots} E_raw[past][series] * exp(-Δ/τ)
    v0: simple forward accumulation; assumes equally-spaced "hour slots".
    """
    slots = to_sorted_slots(E_raw)
    # map slot -> index
    idx = {s:i for i,s in enumerate(slots)}

    E_decay = defaultdict(dict)
    accum = defaultdict(float)

    for i, slot in enumerate(slots):
        # decay existing accum by 1 step each slot
        # (since slots are hourly buckets in v0)
        for s in list(accum.keys()):
            accum[s] *= decay_factor(1)

        # inject new
        for s, e in E_raw[slot].items():
            accum[s] += e

        E_decay[slot] = dict(accum)

    return E_decay

def main():
    in_path = "output/event_maps.jsonl"
    out_path = "event_forcing_v0.2.json"

    if not os.path.exists(in_path):
        raise FileNotFoundError(f"missing {in_path}, run run_bridge.py first")

    E_raw = build_reservoir(in_path)
    E_decay = compute_decayed_series(E_raw)

    payload = {
        "meta": {
            "tau": TAU,
            "lambda_event": LAMBDA_EVENT,
            "slotting": "hourly_bucket_ts[:13]",
            "note": "event forcing is applied to projected feeding (B-mode), not W_avg"
        },
        "E_raw": {k: v for k, v in E_raw.items()},
        "E_decay": {k: v for k, v in E_decay.items()}
    }

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print("done ->", out_path)

if __name__ == "__main__":
    main()
