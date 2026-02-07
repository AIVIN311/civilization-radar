# src/series_canonical.py
import json

DEFAULT_ALIASES = {
  "civilization": "civilization_resilience",
  "civilisation": "civilization_resilience",
  "governance": "algorithmic_governance",
  "identity": "identity_data",
  "synthetic": "synthetic_systems",
  "financial": "monetary_infrastructure",
  "finance": "monetary_infrastructure",
  "monetary": "monetary_infrastructure",
}

def load_series_map(path="config/series_map.json"):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def canonicalize_series(series: str, aliases=None) -> str:
    s = (series or "").strip()
    if not s:
        return "unmapped"
    aliases = aliases or DEFAULT_ALIASES
    return aliases.get(s, s)

def resolve_series_for_domain(domain: str, series_map: dict, aliases=None) -> str:
    d = (domain or "").strip().lower()
    raw = series_map.get(d, "unmapped")
    return canonicalize_series(raw, aliases=aliases)
