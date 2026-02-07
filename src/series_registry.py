import json
import re
from functools import lru_cache
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ALIASES_PATH = ROOT / "config" / "series_aliases.json"


def _norm_series(value: str | None) -> str:
    text = (value or "").strip().lower()
    if not text:
        return ""
    text = re.sub(r"[\s\-]+", "_", text)
    text = re.sub(r"[^a-z0-9_\.]+", "", text)
    return text


@lru_cache(maxsize=1)
def _load_registry():
    payload = json.loads(ALIASES_PATH.read_text(encoding="utf-8"))
    default_series = str(payload.get("default_series", "unmapped"))
    canonical = {str(x) for x in payload.get("canonical_series", [])}
    aliases_raw = payload.get("aliases", {}) or {}
    aliases = {}
    for k, v in aliases_raw.items():
        key = _norm_series(k)
        val = _norm_series(v)
        if key and val:
            aliases[key] = val
    for c in list(canonical):
        aliases[_norm_series(c)] = _norm_series(c)
    canonical.add(_norm_series(default_series))
    return {
        "default": _norm_series(default_series),
        "canonical": canonical,
        "aliases": aliases,
    }


def resolve_series(series_raw: str | None, domain: str | None = None) -> str:
    reg = _load_registry()
    key = _norm_series(series_raw)
    if key in reg["aliases"]:
        return reg["aliases"][key]
    if domain:
        dkey = _norm_series(domain)
        if dkey in reg["aliases"]:
            return reg["aliases"][dkey]
    return reg["default"]


def canonical_series_values() -> set[str]:
    return set(_load_registry()["canonical"])
