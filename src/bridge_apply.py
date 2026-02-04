import json, math
from typing import Dict, Any, List

def clamp(x: float, lo: float=0.0, hi: float=1.0) -> float:
    return max(lo, min(hi, x))

def load_rules(path: str) -> Dict[str,Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def match_rule(ev: Dict[str,Any], rule: Dict[str,Any]) -> bool:
    w = rule["when"]
    et_ok = ev["event_type"] in w.get("event_type", [ev["event_type"]])
    actor_ok = any(a in ev["actor_tags"] for a in w.get("actors_any", []))
    geo_ok = any(g in ev["geo_tags"] for g in w.get("geo_any", []))
    return et_ok and actor_ok and geo_ok

def evidence_strength(ev: Dict[str,Any], rule: Dict[str,Any], conf_model: Dict[str,Any]) -> float:
    w = rule["when"]
    score = 0.0
    E = conf_model["E_evidence_scoring"]
    if ev["event_type"] in w.get("event_type", []):
        score += E["event_type_hit"]
    if any(a in ev["actor_tags"] for a in w.get("actors_any", [])):
        score += E["actors_hit"]
    if any(g in ev["geo_tags"] for g in w.get("geo_any", [])):
        score += E["geo_hit"]
    # topic_or_tags_hit reserved for v0.2+
    return min(score, E.get("cap", 1.0))

def compute_confidence(ev: Dict[str,Any], rule: Dict[str,Any], conf_model: Dict[str,Any]) -> float:
    # R: from source.type mapping table
    R_table = conf_model["R_source_reliability"]
    source_type = (ev.get("source") or {}).get("type","unknown")
    R = R_table.get(source_type, R_table.get("unknown", 0.50))

    E = evidence_strength(ev, rule, conf_model)

    # N: novelty from extractor (already 0~1)
    N = float(ev.get("novelty", 0.5))

    # formula in rules file: 0.2 + 0.5R + 0.2E + 0.1N
    conf = 0.2 + 0.5*R + 0.2*E + 0.1*N
    return clamp(conf, 0.0, 1.0)

def energy_injection(ev: Dict[str,Any], w_base: float, cap: float, confidence: float) -> float:
    """
    Event energy is NOT your final series W.
    It's the injected pulse that your existing decay/gate/merge will absorb.
    Keep it bounded:
      energy = min(cap, w_base) * confidence
    """
    return clamp(min(cap, w_base) * confidence, 0.0, cap)

def apply_bridge(ev: Dict[str,Any], ruleset: Dict[str,Any]) -> Dict[str,Any]:
    alias = (ruleset.get("meta") or {}).get("alias", {})
    conf_model = ruleset["confidence_model"]
    series_catalog = ruleset["series_catalog"]

    matched = []
    for rule in ruleset["rules"]:
        if match_rule(ev, rule):
            matched.append(rule)

    # If nothing matches, fall back to civilization bucket
    if not matched:
        fallback_series = "civilization"
        cap = series_catalog[fallback_series]["default_cap"]
        confidence = 0.2 + 0.5*0.5 + 0.2*0.25 + 0.1*float(ev.get("novelty",0.5))  # mild
        confidence = clamp(confidence)
        return {
            **ev,
            "matched_rules": [],
            "maps": [{
                "series": fallback_series,
                "w_base": 0.15,
                "cap": cap,
                "priority": "secondary",
                "confidence": confidence,
                "energy": energy_injection(ev, 0.15, cap, confidence),
                "evidence": {"rule_id": "fallback_none"}
            }]
        }

    maps = []
    for rule in matched:
        conf = compute_confidence(ev, rule, conf_model)
        for out in rule["then"]:
            s = out["series"]
            s = alias.get(s, s)  # governance -> algorithmic_governance
            cap = out.get("cap", series_catalog.get(s, {}).get("default_cap", 0.5))
            w_base = float(out["w_base"])
            pri = out.get("priority", series_catalog.get(s, {}).get("default_priority", "secondary"))
            maps.append({
                "series": s,
                "w_base": w_base,
                "cap": cap,
                "priority": pri,
                "confidence": conf,
                "energy": energy_injection(ev, w_base, cap, conf),
                "evidence": {"rule_id": rule["rule_id"], "tags": rule.get("evidence_tags", [])}
            })

    # Merge duplicates (same series from multiple rules): take max energy, keep best confidence + provenance
    merged: Dict[str,Any] = {}
    for m in maps:
        s = m["series"]
        if s not in merged:
            merged[s] = m
        else:
            if m["energy"] > merged[s]["energy"]:
                merged[s] = m

    return {**ev, "matched_rules": [r["rule_id"] for r in matched], "maps": list(merged.values())}
