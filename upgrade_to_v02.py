import json
import math
import re
import sqlite3
from collections import defaultdict
from statistics import median

DB = "radar.db"
SIGNALS = "signals.json"

EPS = 1e-6
ALPHA = 0.8   # A 放大係數
BETA = 1.2    # D 放大係數
K = 16        # W 回看 slot 數（16*30m=8小時）
DECAY = 0.92  # 指數衰減：越近權重越大

LEVEL_RANK = {"L1": 1, "L2": 2, "L3": 3}


def load_signals():
    with open(SIGNALS, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    levels = cfg["levels"]
    sigs = cfg["signals"]
    hint = cfg.get("sig_hint_weights", {})
    compiled = []
    for s in sigs:
        rx = [re.compile(p) for p in s.get("match_regex", [])]
        compiled.append({**s, "rx": rx})
    return levels, compiled, hint


def extract_paths(notes: str):
    if not notes:
        return []
    return re.findall(r"/[A-Za-z0-9._\-/]+", notes)


def score_one(req: int, sig: str, notes: str, levels, signals, hint_weights):
    # base heat by req
    heat = math.log10(max(0, req) + 1)

    matched = []
    paths = extract_paths(notes)
    text = (notes or "") + " " + " ".join(paths)

    level_max = "L1"
    weight_sum = 0.0

    for s in signals:
        ok = False

        for a in s.get("match_any", []):
            if a in text:
                ok = True
                break

        if (not ok) and s.get("rx"):
            for rxx in s["rx"]:
                if rxx.search(text):
                    ok = True
                    break

        if ok:
            matched.append(s["id"])
            weight_sum += float(s.get("weight", 0.0))
            lv = s.get("level", "L1")
            if LEVEL_RANK.get(lv, 1) > LEVEL_RANK.get(level_max, 1):
                level_max = lv

    # sig hint bonus
    heat += float(hint_weights.get(sig, hint_weights.get("other", 0.0)))

    # level weight
    level_w = float(levels[level_max]["weight"])
    heat += weight_sum * level_w

    return level_max, heat, matched


def main():
    levels, signals, hint_weights = load_signals()

    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    # 讀 snapshots_v01
    rows = cur.execute("""
        SELECT ts, domain, series, req, sig, notes
        FROM snapshots_v01
        ORDER BY ts ASC
    """).fetchall()

    if not rows:
        raise SystemExit("snapshots_v01 is empty. Run: python seed_from_snapshots.py")

    # 先算每筆 heat / level
    tmp = []
    by_domain_heat = defaultdict(list)
    by_slot_domains_L3 = defaultdict(set)  # ✅ D: 只看 L3 擴散

    for r in rows:
        ts = r["ts"]
        domain = r["domain"]
        series = r["series"] or "unknown"
        req = int(r["req"] or 0)
        sig = (r["sig"] or "other").strip()
        notes = r["notes"] or ""

        level_max, heat, matched = score_one(req, sig, notes, levels, signals, hint_weights)

        tmp.append((
            ts, domain, series, req, sig, notes,
            level_max, heat, json.dumps(matched, ensure_ascii=False)
        ))
        by_domain_heat[domain].append(heat)

        if level_max == "L3":
            by_slot_domains_L3[ts].add(domain)

    # baseline：用全期間中位數（v0.2 demo 先這樣，之後可改 rolling 7d）
    baseline = {d: (median(hs) if hs else 0.0) for d, hs in by_domain_heat.items()}

    # slot active domains
    slot_active = defaultdict(set)
    for ts, domain, *_ in tmp:
        slot_active[ts].add(domain)

    # slot D：L3 domain 比例（同一時段 L3 擴散度）
    slot_D = {}
    for ts, active in slot_active.items():
        l3 = by_slot_domains_L3.get(ts, set())
        slot_D[ts] = (len(l3) / max(1, len(active)))

    # 建表 metrics_v02（重建，避免 UNIQUE 問題）
    cur.execute("DROP TABLE IF EXISTS metrics_v02")
    cur.execute("""
        CREATE TABLE metrics_v02 (
            ts TEXT NOT NULL,
            domain TEXT NOT NULL,
            series TEXT NOT NULL,
            req INTEGER NOT NULL,
            sig TEXT,
            level_max TEXT,
            heat REAL,
            A REAL,
            D REAL,
            Hstar REAL,
            W REAL,
            matched_json TEXT,
            PRIMARY KEY (ts, domain)
        )
    """)

    # 逐筆算 A/D/Hstar，收集成 per-domain 序列，最後再算 W
    per_domain_seq = defaultdict(list)

    for ts, domain, series, req, sig, notes, level_max, heat, matched_json in tmp:
        base = baseline.get(domain, 0.0)
        A = math.log((heat + EPS) / (base + EPS))
        D = float(slot_D.get(ts, 0.0))
        Hstar = heat * (1.0 + ALPHA * max(A, 0.0)) * (1.0 + BETA * D)

        per_domain_seq[domain].append((ts, domain, series, req, sig, level_max, heat, A, D, Hstar, matched_json))

    inserts = []
    for domain, seq in per_domain_seq.items():
        seq.sort(key=lambda x: x[0])  # ts ISO 字串可直接排序
        hstars = [x[9] for x in seq]

        for i, item in enumerate(seq):
            ts, domain, series, req, sig, level_max, heat, A, D, Hstar, matched_json = item

            w = 0.0
            wsum = 0.0
            for j in range(K):
                idx = i - j
                if idx < 0:
                    break
                weight = (DECAY ** j)
                w += hstars[idx] * weight
                wsum += weight

            W = w / max(EPS, wsum)

            # ✅ v0.21：W log 壓縮（指數感）
            if W < 0:
                W = 0.0
            W = math.log1p(W)

            inserts.append((ts, domain, series, req, sig, level_max, heat, A, D, Hstar, W, matched_json))

    cur.executemany("""
        INSERT OR REPLACE INTO metrics_v02
        (ts, domain, series, req, sig, level_max, heat, A, D, Hstar, W, matched_json)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
    """, inserts)

    # views
    cur.execute("DROP VIEW IF EXISTS v02_domain_latest")
    cur.execute("""
        CREATE VIEW v02_domain_latest AS
        SELECT m.*
        FROM metrics_v02 m
        JOIN (
            SELECT domain, MAX(ts) AS ts
            FROM metrics_v02
            GROUP BY domain
        ) x
        ON m.domain = x.domain AND m.ts = x.ts
    """)

    cur.execute("DROP VIEW IF EXISTS v02_series_latest")
    cur.execute("""
        CREATE VIEW v02_series_latest AS
        SELECT ts, series,
               COUNT(*) AS domains,
               AVG(heat) AS heat_avg,
               AVG(A) AS A_avg,
               AVG(D) AS D_avg,
               AVG(Hstar) AS Hstar_avg,
               AVG(W) AS W_avg,
               SUM(CASE WHEN level_max='L3' THEN 1 ELSE 0 END) AS L3_domains
        FROM metrics_v02
        GROUP BY ts, series
    """)

    con.commit()
    con.close()

    print(f"v0.2 done -> metrics_v02 rows={len(inserts)}; views=v02_domain_latest,v02_series_latest")


if __name__ == "__main__":
    main()
