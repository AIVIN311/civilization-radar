import json
from pathlib import Path

SRC = Path("config/domains_50.json")
OUT1 = Path("config/domains_50.fixed.json")  # 保留原檔
OUT2 = Path("domains.json")                  # 給 pipeline 用（如果你想統一）

# 允許的 series（文明力場）
ALLOWED = {
    "algorithmic_governance",
    "monetary_infrastructure",
    "identity_data",
    "civilization_resilience",
    "synthetic_systems",
    "offworld_expansion",
    "human_manifesto",
}

# 你可能曾用過的別名 -> 統一到上面
ALIASES = {
    "governance": "algorithmic_governance",
    "civilization": "civilization_resilience",
    "civilization_resilience": "civilization_resilience",
    "civilization_resillience": "civilization_resilience",
    "identity": "identity_data",
    "identity-data": "identity_data",
    "synthetic": "synthetic_systems",
    "monetary": "monetary_infrastructure",
    "finance": "monetary_infrastructure",
    "financial": "monetary_infrastructure",
}

def norm_domain(s: str) -> str:
    return (s or "").strip().lower()

def norm_series(s: str) -> str:
    s = (s or "").strip()
    s = ALIASES.get(s, s)
    return s if s in ALLOWED else "unknown"

def main():
    data = json.loads(SRC.read_text(encoding="utf-8"))
    fixed = []
    unknown = 0

    for item in data:
        dom = norm_domain(item.get("domain"))
        series = norm_series(item.get("series"))
        prof = (item.get("profile") or "normal").strip()

        if series == "unknown":
            unknown += 1

        fixed.append({"domain": dom, "series": series, "profile": prof})

    OUT1.write_text(json.dumps(fixed, ensure_ascii=False, indent=2), encoding="utf-8")
    OUT2.write_text(json.dumps(fixed, ensure_ascii=False, indent=2), encoding="utf-8")

    print("read:", len(data))
    print("written:", len(fixed))
    print("unknown series count:", unknown)
    print("wrote:", OUT1)
    print("wrote:", OUT2)

if __name__ == "__main__":
    main()
