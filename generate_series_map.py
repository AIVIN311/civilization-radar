import json
import os

INP = "config/domains_50.fixed.json" if os.path.exists("config/domains_50.fixed.json") else "config/domains_50.json"
OUT = "config/series_map.json"

with open(INP, "r", encoding="utf-8") as f:
    data = json.load(f)

# 支援兩種格式：list 或 {"domains":[...]}
items = data["domains"] if isinstance(data, dict) and "domains" in data else data
if not isinstance(items, list):
    raise SystemExit(f"Invalid domains file format: {INP}")

smap = {"default": "civilization"}

count = 0
skipped = 0

for it in items:
    try:
        if isinstance(it, str):
            # 如果是純字串 domain，無法映射 series，跳過
            skipped += 1
            continue

        if not isinstance(it, dict):
            skipped += 1
            continue

        d = it.get("domain") or it.get("name")
        s = it.get("series") or it.get("group")

        if d and s:
            smap[str(d).lower()] = str(s)
            count += 1
        else:
            skipped += 1
    except Exception:
        skipped += 1
        continue

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(smap, f, ensure_ascii=False, indent=2)

print(f"✅ wrote {OUT} from {INP}")
print(f"✅ domains mapped: {count}")
print(f"⚠️ skipped items: {skipped}")
