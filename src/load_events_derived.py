# src/load_events_derived.py
import json
import os
from collections import defaultdict

def load_events_derived(path="output/events_derived.jsonl"):
    """
    Return:
      dict(domain_lower -> list[event])
    event example:
      {"date","domain","series","type","ratio","baseline_avg","current",...}
    """
    if not os.path.exists(path):
        return {}

    mp = defaultdict(list)
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except Exception:
                continue
            dom = e.get("domain")
            if isinstance(dom, str) and dom:
                mp[dom.lower()].append(e)

    # sort per domain by date
    for dom in mp:
        mp[dom].sort(key=lambda x: x.get("date", ""))

    return dict(mp)
