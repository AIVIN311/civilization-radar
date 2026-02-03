import json
import os
import random
import math
from datetime import datetime, timedelta, timezone

CONFIG_PATH = os.path.join("config", "domains_50.json")
OUT_PATH = os.path.join("input", "snapshots.jsonl")

# === 可調參數 ===
SLOT_MINUTES = 30
SLOTS = 32                 # 32*30m=16小時（你要像戰情中心就至少 16 slots 以上）
TZ_OFFSET_HOURS = 8        # +08:00
SEED = 42                  # 固定種子，方便重現
DENSITY = 1.0              # 1.0=每 domain 每 slot 一筆；0.5=稀疏一半

# 系列同步事件（整體文明層發燒）機率
SERIES_SYNC_PROB = 0.10    # 每個 slot 有 10% 機率對某個 series 施加同步加熱
SERIES_SYNC_MULT_RANGE = (1.4, 2.8)

# 探測事件（L3 觸發）機率基底
SCAN_BASE_PROB = 0.015     # 一般 domain 每 slot 發生掃描的機率
SCAN_HONEYPOT_BONUS = 0.08 # honeypot 額外加成

# === profile 參數（決定 req 的大小與波動）===
PROFILE_PARAMS = {
    "background": {"mu": 1.2, "sigma": 0.35, "base": 2},
    "normal":     {"mu": 2.1, "sigma": 0.55, "base": 6},
    "hot":        {"mu": 2.8, "sigma": 0.65, "base": 14},
    "bursty":     {"mu": 2.0, "sigma": 0.70, "base": 6},
    "honeypot":   {"mu": 2.3, "sigma": 0.60, "base": 8},
}

COUNTRIES = ["US", "DE", "FR", "NL", "GB", "JP", "SG", "AU", "TW", "KR", "CA"]
SCAN_SIGS = ["env_scan", "wp_scan", "config_scan"]
OTHER_SIGS = ["baseline", "other"]

ENV_PATHS = ["/.env", "/app/.env", "/config.ini", "/.git/config", "/wp-config.php", "/admin.php", "/phpinfo.php"]
WP_PATHS  = ["/wp-login.php", "/wp-admin/", "/xmlrpc.php", "/wp-content/", "/wp-includes/"]
CFG_PATHS = ["/config.yml", "/config.yaml", "/settings.py", "/secrets.json", "/.docker/config.json"]

def iso(ts: datetime) -> str:
    # 2026-02-03T23:30:00+08:00
    return ts.isoformat(timespec="seconds")

def load_domains():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        arr = json.load(f)
    out = []
    for x in arr:
        domain = (x.get("domain") or "").strip()
        series = (x.get("series") or "unknown").strip()
        profile = (x.get("profile") or "normal").strip()
        if not domain:
            continue
        if profile not in PROFILE_PARAMS:
            profile = "normal"
        out.append({"domain": domain, "series": series, "profile": profile})
    if not out:
        raise SystemExit(f"Empty domains list: {CONFIG_PATH}")
    return out

def lognormal_req(mu: float, sigma: float, base: int) -> int:
    # 用 lognormal 讓 req 有「偏態」更像真實流量
    v = random.lognormvariate(mu, sigma)
    req = int(base + v)
    return max(0, req)

def pick_top_countries(req: int) -> dict:
    # 把 req 分給 2~4 個國家
    k = random.choice([2, 3, 4])
    picks = random.sample(COUNTRIES, k=k)
    # 生成權重
    ws = [random.random() for _ in range(k)]
    s = sum(ws) or 1.0
    ws = [w / s for w in ws]
    # 分配整數
    remaining = req
    out = {}
    for i, c in enumerate(picks):
        if i == k - 1:
            out[c] = remaining
        else:
            part = int(req * ws[i])
            out[c] = part
            remaining -= part
    return out

def make_scan_notes(sig: str) -> str:
    if sig == "env_scan":
        paths = random.sample(ENV_PATHS, k=random.choice([1, 2, 3]))
    elif sig == "wp_scan":
        paths = random.sample(WP_PATHS, k=random.choice([1, 2, 3]))
    else:
        paths = random.sample(CFG_PATHS, k=random.choice([1, 2, 3]))
    return "paths include " + ", ".join(paths)

def generate():
    random.seed(SEED)

    domains = load_domains()
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)

    # 以「現在」往回推 SLOTS 個 slot，讓 dashboard 有曲線可畫
    tz = timezone(timedelta(hours=TZ_OFFSET_HOURS))
    now = datetime.now(tz=tz)
    # 對齊到 30m 邊界
    minute = (now.minute // SLOT_MINUTES) * SLOT_MINUTES
    aligned = now.replace(minute=minute, second=0, microsecond=0)
    start = aligned - timedelta(minutes=SLOT_MINUTES * (SLOTS - 1))

    # 每個 slot 隨機挑一個 series 做「同步加熱」（可為 None）
    all_series = sorted(set(d["series"] for d in domains))
    slot_sync = {}
    for i in range(SLOTS):
        if random.random() < SERIES_SYNC_PROB and all_series:
            s = random.choice(all_series)
            mult = random.uniform(*SERIES_SYNC_MULT_RANGE)
            slot_sync[i] = (s, mult)
        else:
            slot_sync[i] = (None, 1.0)

    rows = []
    for i in range(SLOTS):
        ts = start + timedelta(minutes=SLOT_MINUTES * i)
        sync_series, sync_mult = slot_sync[i]

        for d in domains:
            if random.random() > DENSITY:
                continue

            prof = PROFILE_PARAMS[d["profile"]]
            req = lognormal_req(prof["mu"], prof["sigma"], prof["base"])

            # bursty：偶爾爆發
            if d["profile"] == "bursty" and random.random() < 0.08:
                req = int(req * random.uniform(2.5, 6.0))

            # series 同步加熱
            if sync_series and d["series"] == sync_series:
                req = int(req * sync_mult)

            # 探測事件（掃描）決定 sig / notes / mitigated
            scan_p = SCAN_BASE_PROB
            if d["profile"] == "honeypot":
                scan_p += SCAN_HONEYPOT_BONUS

            is_scan = (random.random() < scan_p)
            if is_scan:
                sig = random.choice(SCAN_SIGS)
                notes = make_scan_notes(sig)
                # 掃描多半被擋：mitigated 比率高
                mitigated = int(req * random.uniform(0.35, 0.85))
            else:
                sig = random.choice(OTHER_SIGS)
                notes = ""
                mitigated = int(req * random.uniform(0.00, 0.10))

            mitigated = max(0, min(mitigated, req))

            # cf/origin 分配（只是用來讓版面看起來像真資料）
            cf_served = int((req - mitigated) * random.uniform(0.15, 0.50))
            origin_served = max(0, (req - mitigated) - cf_served)

            top = pick_top_countries(req)

            rows.append({
                "ts": iso(ts),
                "domain": d["domain"],
                "series": d["series"],
                "req": int(req),
                "mitigated": int(mitigated),
                "cf_served": int(cf_served),
                "origin_served": int(origin_served),
                "top_countries": top,
                "sig": sig,
                "notes": notes
            })

    # 寫 jsonl
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"generated={len(rows)} rows into {OUT_PATH}")
    # 額外印同步事件方便你 sanity check
    sync_events = [(i, s, m) for i, (s, m) in slot_sync.items() if s]
    if sync_events:
        print("series_sync_events (slot_index, series, mult):")
        for i, s, m in sync_events[:10]:
            print(f"  - {i:02d}: {s} x{m:.2f}")
        if len(sync_events) > 10:
            print(f"  ... ({len(sync_events)-10} more)")
    else:
        print("series_sync_events: none")

if __name__ == "__main__":
    generate()
