import json, random, math
from datetime import datetime, timedelta, timezone

TZ = timezone(timedelta(hours=8))
START = datetime(2026, 1, 28, 0, 0, tzinfo=TZ)   # 隨便起點
DAYS = 7
SLOT_MIN = 30

DOMAINS = [
  ("algorithmiclegitimacy.com","governance"),
  ("climateinterventionism.com","civilization"),
  ("postfiatreservesystems.com","monetary_infrastructure"),
  ("biometricsovereignty.com","identity_data"),
  ("syntheticrealitycrisis.com","synthetic_systems"),
]

# 你 signals.json 裡的 sig_hint_weights 會加分；這裡故意讓部分時段有 env_scan
SIGS = ["baseline", "other", "dns_spike", "env_scan"]

def gen_one(ts, domain, series, burst=False):
    base = random.randint(30, 120)
    if burst:
        base *= random.randint(8, 18)  # 做出異常爆量
        sig = "env_scan"
        notes = "paths include /.env, /app/.env, /config.ini"
    else:
        sig = random.choices(SIGS, weights=[70, 20, 8, 2])[0]
        notes = "ok" if sig != "env_scan" else "paths include /.env"
    req = base + random.randint(0, 50)
    mitigated = int(req * random.uniform(0.01, 0.12)) if sig in ("env_scan","dns_spike") else int(req * random.uniform(0.0, 0.03))
    cf_served = int(req * random.uniform(0.2, 0.6))
    origin_served = max(0, req - cf_served)

    top_countries = {"US": random.randint(5, req//2), "FR": random.randint(2, req//3), "NL": random.randint(1, req//4)}
    return {
        "ts": ts.isoformat(),
        "domain": domain,
        "series": series,
        "req": req,
        "mitigated": mitigated,
        "cf_served": cf_served,
        "origin_served": origin_served,
        "top_countries": top_countries,
        "sig": sig,
        "notes": notes
    }

def main():
    out = []
    slots = (DAYS * 24 * 60) // SLOT_MIN

    # 人為安排：第 4 天中午，某個系列一起升溫（擴散事件）
    diffusion_day = 3
    diffusion_slot_center = (diffusion_day * 48) + 24  # 中午附近

    for i in range(slots):
        ts = START + timedelta(minutes=SLOT_MIN * i)

        for (domain, series) in DOMAINS:
            burst = False

            # 擴散：同一個時間窗，2-3 個 domain 同時 env_scan
            if abs(i - diffusion_slot_center) <= 2 and series in ("governance","monetary_infrastructure","identity_data"):
                burst = True

            # 偶發：單點 spike
            if not burst and random.random() < 0.01:
                burst = True

            out.append(gen_one(ts, domain, series, burst=burst))

    with open("input/snapshots.jsonl", "w", encoding="utf-8") as f:
        for row in out:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"generated={len(out)} rows into input/snapshots.jsonl")

if __name__ == "__main__":
    main()
