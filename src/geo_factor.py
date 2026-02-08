import json
from pathlib import Path


DEFAULT_GEO_PROFILES_PATH = Path("config") / "geo_profiles_v1.json"
GEO_PROFILES_VERSION = "geo_profiles_v1"
ALLOWED_PROFILE_KINDS = {"weighted", "baseline"}


def _as_non_negative_float(value, default=0.0):
    try:
        num = float(value)
    except Exception:
        return float(default)
    return num if num >= 0 else float(default)


def _as_non_negative_int(value, default=0):
    try:
        num = int(value)
    except Exception:
        return int(default)
    return num if num >= 0 else int(default)


def _validate_profile(name: str, profile: dict):
    if not isinstance(profile, dict):
        raise ValueError(f"Invalid profile '{name}': must be an object")

    for key in ("enabled", "min_total", "cap_share", "alpha", "weights"):
        if key not in profile:
            raise ValueError(f"Invalid profile '{name}': missing key '{key}'")

    min_total = _as_non_negative_float(profile["min_total"], default=-1.0)
    cap_share = _as_non_negative_float(profile["cap_share"], default=-1.0)
    alpha = _as_non_negative_float(profile["alpha"], default=-1.0)
    weights = profile["weights"]
    kind = str(profile.get("kind", "weighted")).strip().lower()
    min_countries = _as_non_negative_int(profile.get("min_countries", 0), default=-1)

    if min_total < 0:
        raise ValueError(f"Invalid profile '{name}': min_total must be >= 0")
    if cap_share < 0 or cap_share > 1:
        raise ValueError(f"Invalid profile '{name}': cap_share must be in [0, 1]")
    if alpha <= 0:
        raise ValueError(f"Invalid profile '{name}': alpha must be > 0")
    if not isinstance(weights, dict):
        raise ValueError(f"Invalid profile '{name}': weights must be an object")
    if kind not in ALLOWED_PROFILE_KINDS:
        allowed = ", ".join(sorted(ALLOWED_PROFILE_KINDS))
        raise ValueError(f"Invalid profile '{name}': kind must be one of [{allowed}]")
    if min_countries < 0:
        raise ValueError(f"Invalid profile '{name}': min_countries must be >= 0")

    for country, weight in weights.items():
        country_key = str(country).strip().upper()
        if not country_key:
            raise ValueError(f"Invalid profile '{name}': empty country code in weights")
        if _as_non_negative_float(weight, default=-1.0) < 0:
            raise ValueError(f"Invalid profile '{name}': weight for {country_key} must be >= 0")


def load_geo_profiles(path: str | Path = DEFAULT_GEO_PROFILES_PATH) -> dict:
    resolved = Path(path)
    if not resolved.exists():
        raise FileNotFoundError(f"Missing geo profiles file: {resolved}")

    payload = json.loads(resolved.read_text(encoding="utf-8"))
    if payload.get("version") != GEO_PROFILES_VERSION:
        raise ValueError(
            f"Invalid geo profiles version: {payload.get('version')!r}, expected '{GEO_PROFILES_VERSION}'"
        )

    profiles = payload.get("profiles")
    if not isinstance(profiles, dict):
        raise ValueError("Invalid geo profiles: 'profiles' must be an object")

    for required in ("none", "tw", "nearby"):
        if required not in profiles:
            raise ValueError(f"Invalid geo profiles: missing required profile '{required}'")

    normalized = {}
    for name, profile in profiles.items():
        _validate_profile(name, profile)
        weights = {}
        for country, weight in profile["weights"].items():
            country_key = str(country).strip().upper()
            weights[country_key] = float(weight)
        normalized[name] = {
            "enabled": bool(profile["enabled"]),
            "min_total": float(profile["min_total"]),
            "cap_share": float(profile["cap_share"]),
            "alpha": float(profile["alpha"]),
            "kind": str(profile.get("kind", "weighted")).strip().lower() or "weighted",
            "min_countries": _as_non_negative_int(profile.get("min_countries", 0), default=0),
            "weights": weights,
        }

    return normalized


def compute_geo_factor(top_countries: dict | None, profile_name: str, profiles: dict) -> tuple[float, dict]:
    if profile_name not in profiles:
        available = ", ".join(sorted(profiles.keys()))
        raise ValueError(f"Unknown geo profile '{profile_name}'. Available: {available}")

    profile = profiles[profile_name]
    raw_counts = top_countries if isinstance(top_countries, dict) else {}
    counts = {}
    for country, value in raw_counts.items():
        code = str(country).strip().upper()
        if not code:
            continue
        counts[code] = counts.get(code, 0.0) + _as_non_negative_float(value, default=0.0)

    total_counts = float(sum(counts.values()))
    total = max(1.0, total_counts)
    min_total = float(profile["min_total"])
    cap_share = float(profile["cap_share"])
    alpha = float(profile["alpha"])
    kind = str(profile.get("kind", "weighted")).strip().lower() or "weighted"
    min_countries = int(profile.get("min_countries", 0) or 0)
    weights = profile["weights"]

    if kind == "baseline":
        baseline_vector = []
        ranked = sorted(counts.items(), key=lambda x: (-x[1], x[0]))
        distinct_countries = len(ranked)

        if not profile["enabled"]:
            gate = {"passed": False, "reason": "profile_disabled"}
        elif total_counts < min_total:
            gate = {"passed": False, "reason": "insufficient_samples"}
        elif distinct_countries < min_countries:
            gate = {"passed": False, "reason": "insufficient_countries"}
        else:
            capped = []
            sum_capped = 0.0
            for country, count in ranked:
                share = float(count) / total_counts
                share_capped = min(share, cap_share)
                sum_capped += share_capped
                capped.append((country, float(count), share, share_capped))

            if sum_capped <= 1e-12:
                gate = {"passed": False, "reason": "invalid_capped_distribution"}
            else:
                gate = {"passed": True, "reason": "ok"}
                for country, count, share, share_capped in capped:
                    baseline_share = share_capped / sum_capped
                    baseline_vector.append(
                        {
                            "country": country,
                            "count": count,
                            "share": share,
                            "share_capped": share_capped,
                            "baseline_share": baseline_share,
                        }
                    )
                baseline_vector.sort(key=lambda x: (-float(x["baseline_share"]), x["country"]))

        if gate["passed"]:
            geo_factor = 1.0
            raw = 1.0
        else:
            geo_factor = 0.0
            raw = 0.0
            baseline_vector = []

        explain = {
            "version": "geo_explain_v1",
            "profile": profile_name,
            "kind": "baseline",
            "total": total_counts,
            "min_total": min_total,
            "min_countries": min_countries,
            "cap_share": cap_share,
            "alpha": alpha,
            "raw": raw,
            "geo_factor": geo_factor,
            "gate": gate,
            "baseline_vector": baseline_vector[:12],
            "matched": [],
            "unmatched_top": [],
            "notes": [
                "baseline_vector derived from capped and renormalized top_countries shares",
                "geo_factor compatibility scalar: 1.0 when gate passed, else 0.0",
            ],
        }
        return geo_factor, explain

    matched = []
    unmatched_top = []
    raw = 0.0

    ranked = sorted(counts.items(), key=lambda x: (-x[1], x[0]))
    for country, count in ranked:
        share = float(count) / total
        if country in weights:
            weight = float(weights[country])
            share_capped = min(share, cap_share)
            contribution = share_capped * weight
            raw += contribution
            matched.append(
                {
                    "country": country,
                    "count": float(count),
                    "share": share,
                    "share_capped": share_capped,
                    "weight": weight,
                    "contribution": contribution,
                }
            )
        else:
            unmatched_top.append(
                {
                    "country": country,
                    "count": float(count),
                    "share": share,
                }
            )

    if not profile["enabled"]:
        gate = {"passed": False, "reason": "profile_disabled"}
        geo_factor = 0.0
    elif total_counts < min_total:
        gate = {"passed": False, "reason": "insufficient_samples"}
        geo_factor = 0.0
    else:
        gate = {"passed": True, "reason": "ok"}
        geo_factor = raw / (raw + alpha)

    explain = {
        "version": "geo_explain_v1",
        "profile": profile_name,
        "total": total_counts,
        "min_total": min_total,
        "cap_share": cap_share,
        "alpha": alpha,
        "raw": raw,
        "geo_factor": geo_factor,
        "gate": gate,
        "matched": matched,
        "unmatched_top": unmatched_top[:8],
        "notes": [
            "raw = sum(min(share, cap_share) * weight)",
            "geo_factor = raw / (raw + alpha) when gate passed; otherwise 0",
        ],
    }
    return geo_factor, explain


def compute_tw_rank(boosted_score: float, geo_factor: float) -> tuple[float, dict]:
    boosted = float(boosted_score or 0.0)
    geo = float(geo_factor or 0.0)
    multiplier = 1.0 + geo
    tw_rank_score = boosted * multiplier
    explain = {
        "version": "tw_rank_v1",
        "boosted_score": boosted,
        "geo_factor": geo,
        "multiplier": multiplier,
        "tw_rank_score": tw_rank_score,
        "formula": "tw_rank_score = boosted_score * (1 + geo_factor)",
        "base_metric": "boosted_push",
        "reason": "closest to chain push semantics in v0.4; non-interference",
    }
    return tw_rank_score, explain
