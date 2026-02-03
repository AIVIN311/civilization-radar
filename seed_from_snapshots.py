import json
import math
import os
import re
import sqlite3
from datetime import datetime, timezone

DB_PATH = "radar.db"
INPUT_PATH = os.path.join("input", "snapshots.jsonl")
SIGNALS_PATH = "signals.json"

LEVEL_ORDER = {"L1": 1, "L2": 2, "L3": 3}

def safe_int(x, default=0):
    try:
        return int(x)
    except Exception:
        return default

def parse_iso(ts: str) -> str:
    # keep as-is (ISO string) for display
    return ts

def slot_of_iso(ts: str, minutes: int = 30) -> int:
    # Convert ISO -> unix minutes slot (30m buckets)
    # Accept "2026-02-03T15:30:00+08:00" or without tz
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        # fallback: treat as UTC-like
        dt = datetime.strptime(ts[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
    epoch = int(dt.timestamp())
    bucket = minutes * 60
    return epoch // bucket

def load_signals():
    with open(SIGNALS_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    levels = cfg.get("levels", {})
    signals = cfg.get("signals", [])
    sig_hint = cfg.get("sig_hint_weights", {"other": 0.0})

    # precompile regex lists
    compiled = []
    for s in signals:
        entry = dict(s)
        entry["match_regex_compiled"] = []
        for pat in s.get("match_regex", []):
            entry["match_regex_compiled"].append(re.compile(pat, re.IGNORECASE))
        compiled.append(entry)

    return levels, compiled, sig_hint

def match_signals(text: str, compiled_signals):
    """
    Return:
      matched_ids, sum_weight, max_level, toxin_sum (L3 only), hits_count
    """
    t = (text or "").lower()

    matched = []
    sum_w = 0.0
    toxin = 0.0
    max_level = "L1"
    hits = 0

    for s in compiled_signals:
        sid = s.get("id", "")
        level = s.get("level", "L1")
        w = float(s.get("weight", 0.0))

        hit = False

        for token in s.get("match_any", []):
            if token.lower() in t:
                hit = True
                break

        if not hit:
            for rx in s.get("match_regex_compiled", []):
                if rx.search(t):
                    hit = True
                    break

        if hit:
            matched.append(sid)
            sum_w += w
            hits += 1
            if LEVEL_ORDER.get(level, 1) > LEVEL_ORDER.get(max_level, 1):
                max_level = level
            if level == "L3":
                toxin += w

    return matched, sum_w, max_level, toxin, hits

def compute_scores(req: int, sig: str, notes: str, levels_cfg, compiled_signals, sig_hint_weights):
    # base: log scale of traffic
    base = math.log10(req + 1)

    # sig hint bonus (coarse classifier)
    sig_key = (sig or "other").strip()
    sig_bonus = float(sig_hint_weights.get(sig_key, sig_hint_weights.get("other", 0.0)))

    # signal matching from notes (paths, hints)
    matched_ids, sum_w, max_level, toxin_sum, hits = match_signals(notes or "", compiled_signals)

    # level weight multiplier
    level_w = float(levels_cfg.get(max_level, {}).get("weight", 1.0))

    # heat: base traffic + sig bonus + (signal weights * level weight)
    heat = base + sig_bonus + (sum_w * level_w)

    # toxin: normalize a bit so it doesn't explode; still meaningful
    toxin = toxin_sum  # keep raw for now (v0.1)
    toxin = round(toxin, 3)

    return {
        "level_max": max_level,
        "heat": round(heat, 3),
        "toxin": toxin,
        "matched": matched_ids,
        "hits": hits,
        "sig_bonus": round(sig_bonus, 3)
    }

def ensure_schema(conn: sqlite3.Connection):
    conn.execute("""
    CREATE TABLE IF NOT EXISTS snapshots_v01 (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      ts TEXT NOT NULL,
      slot INTEGER NOT NULL,
      domain TEXT NOT NULL,
      series TEXT NOT NULL,
      req INTEGER NOT NULL,
      mitigated INTEGER DEFAULT 0,
      cf_served INTEGER DEFAULT 0,
      origin_served INTEGER DEFAULT 0,
      top_countries TEXT DEFAULT '{}',
      sig TEXT DEFAULT 'other',
      notes TEXT DEFAULT '',
      level_max TEXT DEFAULT 'L1',
      heat REAL DEFAULT 0.0,
      toxin REAL DEFAULT 0.0,
      matched TEXT DEFAULT '[]'
    );
    """)

    conn.execute("CREATE INDEX IF NOT EXISTS idx_snapshots_v01_slot ON snapshots_v01(slot);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_snapshots_v01_domain ON snapshots_v01(domain);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_snapshots_v01_series ON snapshots_v01(series);")

    # optional convenience views for dashboard queries
    conn.execute("""
    CREATE VIEW IF NOT EXISTS v01_domain_latest AS
    SELECT s.*
    FROM snapshots_v01 s
    JOIN (
      SELECT domain, MAX(slot) AS max_slot
      FROM snapshots_v01
      GROUP BY domain
    ) m ON s.domain = m.domain AND s.slot = m.max_slot;
    """)

    conn.execute("""
    CREATE VIEW IF NOT EXISTS v01_series_latest AS
    SELECT series, SUM(req) AS req_sum, MAX(slot) AS slot
    FROM v01_domain_latest
    GROUP BY series;
    """)

def read_jsonl(path: str):
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)

def main():
    if not os.path.exists(INPUT_PATH):
        raise FileNotFoundError(f"Missing {INPUT_PATH}. Put snapshots.jsonl under /input")

    levels_cfg, compiled_signals, sig_hint_weights = load_signals()

    conn = sqlite3.connect(DB_PATH)
    ensure_schema(conn)

    inserted = 0

    for row in read_jsonl(INPUT_PATH):
        ts = parse_iso(row.get("ts", ""))
        domain = (row.get("domain") or "").strip()
        series = (row.get("series") or "unknown").strip()
        req = safe_int(row.get("req"), 0)

        mitigated = safe_int(row.get("mitigated"), 0)
        cf_served = safe_int(row.get("cf_served"), 0)
        origin_served = safe_int(row.get("origin_served"), 0)

        top_countries = row.get("top_countries") or {}
        sig = (row.get("sig") or "other").strip()
        notes = row.get("notes") or ""

        slot = slot_of_iso(ts, minutes=30)

        scores = compute_scores(
            req=req,
            sig=sig,
            notes=notes,
            levels_cfg=levels_cfg,
            compiled_signals=compiled_signals,
            sig_hint_weights=sig_hint_weights
        )

        conn.execute(
            """
            INSERT INTO snapshots_v01
            (ts, slot, domain, series, req, mitigated, cf_served, origin_served,
             top_countries, sig, notes, level_max, heat, toxin, matched)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ts, slot, domain, series, req, mitigated, cf_served, origin_served,
                json.dumps(top_countries, ensure_ascii=False),
                sig, notes,
                scores["level_max"],
                scores["heat"],
                scores["toxin"],
                json.dumps(scores["matched"], ensure_ascii=False)
            )
        )
        inserted += 1

    conn.commit()
    conn.close()

    print(f"seeded v0.1 -> {DB_PATH} (snapshots_v01). inserted={inserted}")

if __name__ == "__main__":
    main()
