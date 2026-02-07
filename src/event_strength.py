# src/event_strength.py
import math

def event_strength(baseline_avg, current, origin_served=0, cf_served=0) -> float:
    b = max(1.0, float(baseline_avg or 0.0))
    c = max(0.0, float(current or 0.0))
    delta = max(0.0, c - b)
    ratio = c / b

    # 比例強度（翻倍=1，四倍=2）
    s_ratio = max(0.0, math.log(ratio, 2))

    # 量級強度（delta 相對 baseline，用 log 壓縮避免爆）
    s_delta = math.log1p(delta / b)

    # 來源偏差：CF 高→略降，Origin 高→略升（幅度小）
    tot = max(1.0, float((origin_served or 0) + (cf_served or 0)))
    cf_share = float(cf_served or 0) / tot
    s_src = (0.5 - cf_share) * 0.6   # 約 -0.3..+0.3

    raw = 2.2*s_ratio + 2.0*s_delta + s_src
    score = max(0.0, min(10.0, raw * 2.0))
    return float(score)
