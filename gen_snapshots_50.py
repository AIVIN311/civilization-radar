import os, json, random
from datetime import datetime, timedelta, timezone

# === Mapping sources (priority order) ===
MAPPING_CANDIDATES = [
    "domains.json",                       # fix_domains_50.py 產出的正式版
    os.path.join("config","domains_50.fixed.json"),
    os.path.join("config","domains_50.json"),  # 舊檔最後才用
]

OUT_PATH = os.path.join("input", "snapshots.jsonl")

SLOT_MINUTES = 30
SLOTS = 32
DOMAINS_PER_SLOT = 50


# -------------------------
# Load domain mappings
# -------------------------

def load_domains():

    for path in MAPPING_CANDIDATES:
        if os.path.exists(path):
            with open(path,"r",encoding="utf-8") as f:
                arr = json.load(f)

            mp = {}
            for it in arr:
                d = (it.get("domain") or "").strip().lower()
                if not d:
                    continue
                mp[d] = {
                    "series": it.get("series"),
                    "profile": it.get("profile","normal")
                }

            print("loaded mappings from:", path, "rows:", len(mp))
            return mp

    raise FileNotFoundError("No domain mapping file found!")


# -------------------------
# Helpers
# -------------------------

def iso(ts: datetime) -> str:
    return ts.isoformat(timespec="seconds")


def pick_top_countries():
    pool = ["TW","US","JP","KR","SG","GB","DE","FR","NL","AU","CA"]
    k = random.randint(2, 4)
    cs = random.sample(pool, k)
    return {c: random.randint(0, 22) for c in cs}


# -------------------------
# Event generator
# -------------------------

def gen_event(profile: str):

    if profile == "hot":
        req = random.randint(18, 60)
    elif profile == "honeypot":
        req = random.randint(10, 45)
    else:
        req = random.randint(6, 28)

    r = random.random()

    if profile == "honeypot" and r < 0.35:
        sig = random.choice(["env_scan", "config_scan", "wp_scan"])
    elif r < 0.10:
        sig = random.choice(["env_scan", "config_scan"])
    elif r < 0.55:
        sig = "baseline"
    else:
        sig = "other"

    notes = ""
    mitigated = 0

    if sig == "env_scan":
        notes = "paths include /.env, /app/.env"
        mitigated = random.randint(0, int(req * 0.8))
    elif sig == "config_scan":
        notes = "paths include /config.ini, /wp-config.php"
        mitigated = random.randint(0, int(req * 0.6))
    elif sig == "wp_scan":
        notes = "paths include /wp-login.php, /xmlrpc.php"
        mitigated = random.randint(0, int(req * 0.5))
    else:
        mitigated = random.randint(0, int(req * 0.1))

    cf_served = random.randint(0, req)
    origin_served = max(0, req - cf_served)

    return req, mitigated, cf_served, origin_served, sig, notes


# -------------------------
# Main pipeline
# -------------------------

def main():

    mp = load_domains()

    # 🔥 Hard validation (no silent unknown)
    bad = [d for d,v in mp.items() if v.get("series") in (None,"","unknown")]

    if bad:
        print("FATAL: series missing/unknown for", len(bad), "domains")
        print("examples:", bad[:10])
        raise SystemExit(2)

    domains = sorted(mp.keys())

    print("sample mapping:", domains[0], "->", mp[domains[0]])

    tz = timezone(timedelta(hours=8))
    now = datetime.now(tz=tz)

    minute = (now.minute // SLOT_MINUTES) * SLOT_MINUTES
    start = now.replace(minute=minute, second=0, microsecond=0) - timedelta(
        minutes=SLOT_MINUTES * SLOTS
    )

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)

    written = 0

    with open(OUT_PATH, "w", encoding="utf-8") as f:

        for si in range(SLOTS):

            ts = start + timedelta(minutes=SLOT_MINUTES * si)
            ts_str = iso(ts)

            for d in domains[:DOMAINS_PER_SLOT]:

                info = mp[d]
                series = info["series"]
                profile = info["profile"]

                req, mitigated, cf_served, origin_served, sig, notes = gen_event(profile)

                row = {
                    "ts": ts_str,
                    "domain": d,
                    "series": series,      # ✅ 這次一定是真實場域
                    "req": req,
                    "mitigated": mitigated,
                    "cf_served": cf_served,
                    "origin_served": origin_served,
                    "top_countries": pick_top_countries(),
                    "sig": sig,
                    "notes": notes,
                }

                f.write(json.dumps(row, ensure_ascii=False) + "\n")
                written += 1

    print(f"generated={written} rows into {OUT_PATH}")
    print("mapping OK: all domains had valid series/profile")


if __name__ == "__main__":
    main()
