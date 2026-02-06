import json, os

INP = "config/domains_50.fixed.json" if os.path.exists("config/domains_50.fixed.json") else "config/domains_50.json"
OUT = "config/series_map.json"

with open(INP, "r", encoding="utf-8") as f:
    data = json.load(f)

# 支援兩種格式：list 或 {"domains":[...]}
items = data["domains"] if isinstance(data, dict) and "domains" in data else data

smap = {"default": "civilization"}

for it in items:
    d = it.get("domain") or it.get("name")
    s = it.get("series") or it.get("group")
    if d and s:
        smap[d.lower()] = s

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(smap, f, ensure_ascii=False, indent=2)

print(f"✅ wrote {OUT} from {INP}  (domains mapped: {len(smap)-1})")
