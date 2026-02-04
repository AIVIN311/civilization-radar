import json
from src.extract_v0_1 import extract_event
from src.bridge_apply import load_rules, apply_bridge

def main():
    ruleset = load_rules("bridge_rules_v0.4.json")
    fp_counts = {}

    with open("input/events.jsonl", "r", encoding="utf-8") as f_in, \
         open("output/event_maps.jsonl", "w", encoding="utf-8") as f_out:
        for line in f_in:
            raw = json.loads(line)
            ev = extract_event(raw, fp_counts)
            out = apply_bridge(ev, ruleset)
            f_out.write(json.dumps(out, ensure_ascii=False) + "\n")

    print("done -> output/event_maps.jsonl")

if __name__ == "__main__":
    main()
