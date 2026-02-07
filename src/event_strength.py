import math

def clamp(x, lo=0.0, hi=10.0):
    return max(lo, min(hi, x))


def event_strength_explain(
    baseline_avg: float,
    current: float,
    origin_served: float = 0.0,
    cf_served: float = 0.0,
):
    baseline_avg = float(baseline_avg or 0.0)
    current = float(current or 0.0)
    origin_served = float(origin_served or 0.0)
    cf_served = float(cf_served or 0.0)

    out = {
        "ratio": 0.0,
        "origin_share": 0.0,
        "cf_share": 0.0,
        "base_component": 0.0,
        "origin_amp": 1.0,
        "cf_penalty": 1.0,
        "volume_guard": 0.0,
        "strength_final": 0.0,
    }

    if baseline_avg <= 0 or current <= 0:
        return out

    ratio = current / baseline_avg
    total = max(origin_served + cf_served, 1.0)
    origin_share = origin_served / total
    cf_share = cf_served / total
    base = math.log2(1 + ratio) * 4.0
    origin_weight = 1.0 + min(origin_share * 0.8, 0.8)
    cf_penalty = 1.0 - min(cf_share * 0.4, 0.4)
    volume_guard = min(math.log10(current + 1), 3.0)
    raw = base * origin_weight * cf_penalty * volume_guard
    final = round(clamp(raw), 2)

    out.update(
        {
            "ratio": round(ratio, 4),
            "origin_share": round(origin_share, 4),
            "cf_share": round(cf_share, 4),
            "base_component": round(base, 4),
            "origin_amp": round(origin_weight, 4),
            "cf_penalty": round(cf_penalty, 4),
            "volume_guard": round(volume_guard, 4),
            "strength_final": final,
        }
    )
    return out


def event_strength_v11(
    baseline_avg: float,
    current: float,
    origin_served: float = 0.0,
    cf_served: float = 0.0,
):
    return float(
        event_strength_explain(
            baseline_avg=baseline_avg,
            current=current,
            origin_served=origin_served,
            cf_served=cf_served,
        )["strength_final"]
    )


# backward-compatible name used by existing scripts
def event_strength(
    baseline_avg: float,
    current: float,
    origin_served: float = 0.0,
    cf_served: float = 0.0,
):
    return event_strength_v11(
        baseline_avg=baseline_avg,
        current=current,
        origin_served=origin_served,
        cf_served=cf_served,
    )
