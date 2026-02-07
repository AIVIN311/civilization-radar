import math

def event_boost(max_strength: float) -> float:
    """
    Convert event strength (0–10) into a multiplicative chain boost.
    """
    if not max_strength or max_strength <= 0:
        return 1.0
    return 1.0 + math.log1p(max_strength) / 2.0
