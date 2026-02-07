import argparse
import json
import math
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from src.series_registry import resolve_series
from src.settings import add_common_args, from_args


LEVEL_ORDER = {"L1": 1, "L2": 2, "L3": 3}
SCHEMA_VERSION = "v0.4"
DEFAULT_INPUT_PATH = Path("input") / "snapshots.jsonl"
SIGNALS_PATH = Path("signals.json")


def safe_int(x, default=0):
    try:
        return int(x)
    except Exception:
        return default


def parse_iso(ts: str) -> str:
    return ts


def slot_of_iso(ts: str, minutes: int = 30) -> int:
    try:
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except Exception:
        dt = datetime.strptime(str(ts)[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
    epoch = int(dt.timestamp())
    bucket = minutes * 60
    return epoch // bucket


def load_signals():
    cfg = json.loads(SIGNALS_PATH.read_text(encoding="utf-8"))
    levels = cfg.get("levels", {})
    signals = cfg.get("signals", [])
    sig_hint = cfg.get("sig_hint_weights", {"other": 0.0})
    compiled = []
    for s in signals:
        entry = dict(s)
        entry["match_regex_compiled"] = []
        for pat in s.get("match_regex", []):
            import re

            entry["match_regex_compiled"].append(re.compile(pat, re.IGNORECASE))
        compiled.append(entry)
    return levels, compiled, sig_hint


def match_signals(text: str, compiled_signals):
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
            if str(token).lower() in t:
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
    base = math.log10(req + 1)
    sig_key = (sig or "other").strip()
    sig_bonus = float(sig_hint_weights.get(sig_key, sig_hint_weights.get("other", 0.0)))
    matched_ids, sum_w, max_level, toxin_sum, hits = match_signals(notes or "", compiled_signals)
    level_w = float(levels_cfg.get(max_level, {}).get("weight", 1.0))
    heat = base + sig_bonus + (sum_w * level_w)
    return {
        "level_max": max_level,
        "heat": round(heat, 3),
        "toxin": round(toxin_sum, 3),
        "matched": matched_ids,
        "hits": hits,
        "sig_bonus": round(sig_bonus, 3),
    }


def ensure_schema(conn: sqlite3.Connection):
    conn.execute(
        """
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
      matched TEXT DEFAULT '[]',
      missing_fields_json TEXT DEFAULT '[]',
      extra_fields_json TEXT DEFAULT '[]',
      schema_version TEXT DEFAULT 'v0.4'
    );
    """
    )
    cols = {r[1] for r in conn.execute("PRAGMA table_info(snapshots_v01)").fetchall()}
    if "missing_fields_json" not in cols:
        conn.execute("ALTER TABLE snapshots_v01 ADD COLUMN missing_fields_json TEXT DEFAULT '[]'")
    if "extra_fields_json" not in cols:
        conn.execute("ALTER TABLE snapshots_v01 ADD COLUMN extra_fields_json TEXT DEFAULT '[]'")
    if "schema_version" not in cols:
        conn.execute("ALTER TABLE snapshots_v01 ADD COLUMN schema_version TEXT DEFAULT 'v0.4'")

    conn.execute("CREATE INDEX IF NOT EXISTS idx_snapshots_v01_slot ON snapshots_v01(slot);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_snapshots_v01_domain ON snapshots_v01(domain);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_snapshots_v01_series ON snapshots_v01(series);")

    conn.execute(
        """
    CREATE VIEW IF NOT EXISTS v01_domain_latest AS
    SELECT s.*
    FROM snapshots_v01 s
    JOIN (
      SELECT domain, MAX(slot) AS max_slot
      FROM snapshots_v01
      GROUP BY domain
    ) m ON s.domain = m.domain AND s.slot = m.max_slot;
    """
    )
    conn.execute(
        """
    CREATE VIEW IF NOT EXISTS v01_series_latest AS
    SELECT series, SUM(req) AS req_sum, MAX(slot) AS slot
    FROM v01_domain_latest
    GROUP BY series;
    """
    )


def read_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def _text(v, default=""):
    if v is None:
        return default
    t = str(v).strip()
    return t if t else default


def _choose(row: dict, keys: list[str], default=None):
    for k in keys:
        if k in row and row.get(k) is not None:
            return row.get(k), k
    return default, None


def normalize_row(row: dict):
    known_keys = {
        "ts",
        "timestamp",
        "date",
        "domain",
        "series",
        "series_raw",
        "req",
        "requests",
        "dns_total",
        "mitigated",
        "cf_served",
        "origin_served",
        "top_countries",
        "sig",
        "notes",
    }
    missing = []
    ts_raw, ts_src = _choose(row, ["ts", "timestamp"])
    if ts_src is None:
        date_raw, date_src = _choose(row, ["date"])
        if date_src is None:
            ts_raw = "1970-01-01T00:00:00+00:00"
            missing.append("ts")
        else:
            ts_raw = f"{date_raw}T00:00:00+00:00"
    ts = parse_iso(_text(ts_raw, "1970-01-01T00:00:00+00:00"))

    domain_raw, domain_src = _choose(row, ["domain"])
    if domain_src is None:
        missing.append("domain")
    domain = _text(domain_raw, "unknown.domain").lower()

    series_raw, series_src = _choose(row, ["series", "series_raw"])
    if series_src is None:
        missing.append("series")
    series = resolve_series(_text(series_raw, ""), domain)

    req_raw, req_src = _choose(row, ["req", "dns_total", "requests"], 0)
    if req_src is None:
        missing.append("req")
    req = safe_int(req_raw, 0)

    cf_raw, cf_src = _choose(row, ["cf_served"], 0)
    if cf_src is None:
        missing.append("cf_served")
    cf_served = safe_int(cf_raw, 0)

    origin_raw, origin_src = _choose(row, ["origin_served"], 0)
    if origin_src is None:
        missing.append("origin_served")
    origin_served = safe_int(origin_raw, max(0, req - cf_served))

    mitigated_raw, mitigated_src = _choose(row, ["mitigated"], 0)
    if mitigated_src is None:
        missing.append("mitigated")
    mitigated = safe_int(mitigated_raw, 0)

    tc_raw, tc_src = _choose(row, ["top_countries"], {})
    if tc_src is None:
        missing.append("top_countries")
    top_countries = tc_raw if isinstance(tc_raw, dict) else {}

    sig_raw, sig_src = _choose(row, ["sig"], "other")
    if sig_src is None:
        missing.append("sig")
    sig = _text(sig_raw, "other")

    notes_raw, notes_src = _choose(row, ["notes"], "")
    if notes_src is None:
        missing.append("notes")
    notes = _text(notes_raw, "")

    extra_fields = sorted(k for k in row.keys() if k not in known_keys)

    return {
        "ts": ts,
        "domain": domain,
        "series": series,
        "req": req,
        "mitigated": mitigated,
        "cf_served": cf_served,
        "origin_served": origin_served,
        "top_countries": top_countries,
        "sig": sig,
        "notes": notes,
        "missing_fields_json": json.dumps(sorted(set(missing)), ensure_ascii=False),
        "extra_fields_json": json.dumps(extra_fields, ensure_ascii=False),
        "schema_version": SCHEMA_VERSION,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        default=str(DEFAULT_INPUT_PATH),
        help="Path to snapshots jsonl (default: input/snapshots.jsonl)",
    )
    add_common_args(parser)
    args = parser.parse_args()
    cfg = from_args(args)

    in_path = Path(args.input)
    if not in_path.exists():
        raise FileNotFoundError(f"Missing {in_path}. Put snapshots jsonl under /input")

    levels_cfg, compiled_signals, sig_hint_weights = load_signals()

    conn = sqlite3.connect(cfg["db_path"])
    ensure_schema(conn)
    inserted = 0

    for raw in read_jsonl(in_path):
        row = normalize_row(raw)
        slot = slot_of_iso(row["ts"], minutes=30)
        scores = compute_scores(
            req=row["req"],
            sig=row["sig"],
            notes=row["notes"],
            levels_cfg=levels_cfg,
            compiled_signals=compiled_signals,
            sig_hint_weights=sig_hint_weights,
        )
        conn.execute(
            """
            INSERT INTO snapshots_v01
            (ts, slot, domain, series, req, mitigated, cf_served, origin_served,
             top_countries, sig, notes, level_max, heat, toxin, matched,
             missing_fields_json, extra_fields_json, schema_version)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["ts"],
                slot,
                row["domain"],
                row["series"],
                row["req"],
                row["mitigated"],
                row["cf_served"],
                row["origin_served"],
                json.dumps(row["top_countries"], ensure_ascii=False),
                row["sig"],
                row["notes"],
                scores["level_max"],
                scores["heat"],
                scores["toxin"],
                json.dumps(scores["matched"], ensure_ascii=False),
                row["missing_fields_json"],
                row["extra_fields_json"],
                row["schema_version"],
            ),
        )
        inserted += 1

    conn.commit()
    conn.close()
    print(f"seeded v0.4 -> {cfg['db_path']} (snapshots_v01). inserted={inserted}")


if __name__ == "__main__":
    main()
