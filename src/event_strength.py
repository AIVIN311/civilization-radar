import math

def clamp(x, lo=0.0, hi=10.0):
    return max(lo, min(hi, x))

def event_strength_v11(
    baseline_avg: float,
    current: float,
    origin_served: float = 0.0,
    cf_served: float = 0.0,
):
    # --- safety ---
    if baseline_avg <= 0 or current <= 0:
        return 0.0

    # --- ratios ---
    ratio = current / baseline_avg

    total = max(origin_served + cf_served, 1.0)
    origin_share = origin_served / total
    cf_share = cf_served / total

    # --- (A) base anomaly ---
    base = math.log2(1 + ratio) * 4.0

    # --- (B) origin amplification ---
    origin_weight = 1.0 + min(origin_share * 0.8, 0.8)

    # --- (C) cf buffering penalty ---
    cf_penalty = 1.0 - min(cf_share * 0.4, 0.4)

    # --- (D) volume guard ---
    volume_guard = min(math.log10(current + 1), 3.0)

    raw = base * origin_weight * cf_penalty * volume_guard
    return round(clamp(raw), 2)
