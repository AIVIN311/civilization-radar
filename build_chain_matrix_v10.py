import argparse
import json
import math
import os
import sqlite3
from dataclasses import dataclass
from datetime import date

from src.chain_event_boost import event_boost
from src.series_registry import resolve_series
from src.settings import add_common_args, from_args


K = 16
TH_SUS = 1.80
TAU = 12.0
EVENT_FORCING_PATH = "event_forcing_v0.2.json"
DEBUG_EVENT_FORCING = False
LEVEL_RANK = {"L1": 1, "L2": 2, "L3": 3}


def pearson(x, y):
    n = min(len(x), len(y))
    if n < 4:
        return 0.0
    x = x[-n:]
    y = y[-n:]
    mx = sum(x) / n
    my = sum(y) / n
    vx = sum((a - mx) ** 2 for a in x)
    vy = sum((b - my) ** 2 for b in y)
    if vx <= 1e-12 or vy <= 1e-12:
        return 0.0
    cov = sum((x[i] - mx) * (y[i] - my) for i in range(n))
    return cov / math.sqrt(vx * vy)


def detect_level_col(cur):
    cols = [r[1] for r in cur.execute("PRAGMA table_info(metrics_v02)").fetchall()]
    for c in ["level_max", "level", "lvl"]:
        if c in cols:
            return c
    return None


def parse_ymd(text):
    if not text:
        return None
    try:
        return date.fromisoformat(str(text)[:10])
    except Exception:
        return None


@dataclass
class EventProfile:
    event_date: str
    event_type: str
    strength: float
    decayed_strength: float
    boost: float
    level: str
    matched_signals_json: str


def load_event_forcing():
    if os.path.exists(EVENT_FORCING_PATH):
        try:
            payload = json.loads(open(EVENT_FORCING_PATH, "r", encoding="utf-8").read())
            return payload.get("E_decay", {}) or {}
        except Exception:
            return {}
    return {}


def build_event_profile(events, asof_day, half_life_days: float) -> EventProfile:
    if not asof_day or not events:
        return EventProfile("", "", 0.0, 0.0, 1.0, "L1", "[]")
    decay_lambda = math.log(2.0) / max(0.001, half_life_days)
    best = None
    best_val = 0.0
    for e in events:
        age_days = (asof_day - e["day"]).days
        if age_days < 0:
            continue
        decayed = float(e["strength"]) * math.exp(-decay_lambda * age_days)
        if decayed > best_val:
            best_val = decayed
            best = e
        elif abs(decayed - best_val) <= 1e-9 and best is not None:
            if LEVEL_RANK.get(str(e.get("event_level") or "L1"), 1) > LEVEL_RANK.get(
                str(best.get("event_level") or "L1"), 1
            ):
                best = e
    if not best:
        return EventProfile("", "", 0.0, 0.0, 1.0, "L1", "[]")
    return EventProfile(
        event_date=best["date"],
        event_type=best["event_type"],
        strength=float(best["strength"]),
        decayed_strength=float(best_val),
        boost=float(event_boost(best_val)),
        level=str(best.get("event_level") or "L1"),
        matched_signals_json=str(best.get("matched_signals_json") or "[]"),
    )


def prepare_tables(cur):
    cur.executescript(
        """
    DROP TABLE IF EXISTS chain_edges_v10;
    DROP TABLE IF EXISTS chain_edges_decay_latest;
    DROP TABLE IF EXISTS series_chain_v10;
    DROP TABLE IF EXISTS series_chain_decay_latest;

    CREATE TABLE chain_edges_v10 (
      ts TEXT NOT NULL,
      src_series TEXT NOT NULL,
      dst_series TEXT NOT NULL,
      corr REAL NOT NULL,
      dW_src REAL NOT NULL,
      boost_multiplier REAL NOT NULL,
      base_score REAL NOT NULL,
      boosted_score REAL NOT NULL,
      delta_boost REAL NOT NULL,
      push REAL NOT NULL,
      push_raw REAL NOT NULL,
      src_event_date TEXT,
      src_event_type TEXT,
      src_event_strength REAL NOT NULL,
      src_event_decayed_strength REAL NOT NULL,
      max_event_level TEXT,
      src_matched_signals_json TEXT,
      PRIMARY KEY (ts, src_series, dst_series)
    );

    CREATE TABLE chain_edges_decay_latest (
      ts TEXT NOT NULL,
      src_series TEXT NOT NULL,
      dst_series TEXT NOT NULL,
      share REAL NOT NULL,
      base_score REAL NOT NULL,
      boosted_score REAL NOT NULL,
      delta_boost REAL NOT NULL,
      boost_multiplier REAL NOT NULL,
      push REAL NOT NULL,
      push_raw REAL NOT NULL,
      edge_n INTEGER NOT NULL,
      src_event_date TEXT,
      src_event_type TEXT,
      src_event_strength REAL NOT NULL,
      src_event_decayed_strength REAL NOT NULL,
      max_event_level TEXT,
      src_matched_signals_json TEXT,
      PRIMARY KEY (src_series, dst_series)
    );

    CREATE TABLE series_chain_v10 (
      ts TEXT NOT NULL,
      series TEXT NOT NULL,
      W_avg REAL NOT NULL,
      W_proj REAL NOT NULL,
      status TEXT NOT NULL,
      chain_flag INTEGER NOT NULL,
      top_src TEXT,
      share REAL NOT NULL,
      push REAL NOT NULL,
      push_raw REAL NOT NULL,
      base_push REAL NOT NULL,
      boosted_push REAL NOT NULL,
      delta_boost REAL NOT NULL,
      domains INTEGER NOT NULL,
      L3_domains INTEGER NOT NULL,
      max_event_level TEXT,
      PRIMARY KEY (ts, series)
    );

    CREATE TABLE series_chain_decay_latest (
      ts TEXT NOT NULL,
      series TEXT NOT NULL,
      W_avg REAL NOT NULL,
      W_proj REAL NOT NULL,
      status TEXT NOT NULL,
      chain_flag INTEGER NOT NULL,
      top_src TEXT,
      share REAL NOT NULL,
      push REAL NOT NULL,
      push_raw REAL NOT NULL,
      base_push REAL NOT NULL,
      boosted_push REAL NOT NULL,
      delta_boost REAL NOT NULL,
      domains INTEGER NOT NULL,
      L3_domains INTEGER NOT NULL,
      max_event_level TEXT,
      PRIMARY KEY (ts, series)
    );

    CREATE INDEX idx_edges_ts_dst ON chain_edges_v10(ts, dst_series);
    CREATE INDEX idx_series_ts ON series_chain_v10(ts);
    """
    )


def merge_level(a: str, b: str) -> str:
    return a if LEVEL_RANK.get(a, 1) >= LEVEL_RANK.get(b, 1) else b


def main():
    parser = argparse.ArgumentParser()
    add_common_args(parser, include_half_life=True)
    args = parser.parse_args()
    cfg = from_args(args)

    con = sqlite3.connect(cfg["db_path"])
    cur = con.cursor()
    latest = cur.execute("SELECT MAX(ts) FROM metrics_v02").fetchone()[0]
    if not latest:
        raise SystemExit("FATAL: metrics_v02 empty. Run upgrade_to_v02.py first.")

    level_col = detect_level_col(cur)
    E_DECAY = load_event_forcing()

    events_by_series = {}
    try:
        rows = cur.execute(
            """
            SELECT series, date, COALESCE(strength,0.0), COALESCE(event_type,''), COALESCE(event_level,'L1'), COALESCE(matched_signals_json,'[]')
            FROM events_v01
            WHERE series IS NOT NULL
            """
        ).fetchall()
        for s, d, strength, et, el, ms in rows:
            if not s or d is None:
                continue
            ev_day = parse_ymd(d)
            if ev_day is None:
                continue
            series = resolve_series(str(s))
            events_by_series.setdefault(series, []).append(
                {
                    "day": ev_day,
                    "date": str(d),
                    "strength": float(strength or 0.0),
                    "event_type": str(et or ""),
                    "event_level": str(el or "L1"),
                    "matched_signals_json": str(ms or "[]"),
                }
            )
    except sqlite3.OperationalError:
        events_by_series = {}

    ts_list = [r[0] for r in cur.execute("SELECT DISTINCT ts FROM metrics_v02 ORDER BY ts").fetchall()]
    series_list = [
        resolve_series(r[0])
        for r in cur.execute("SELECT DISTINCT series FROM metrics_v02 ORDER BY series").fetchall()
    ]
    series_list = sorted(set(series_list))

    wavg = {}
    dom_count = {}
    l3_count = {}
    if level_col:
        rows = cur.execute(
            f"""
            SELECT ts, series, AVG(COALESCE(W,0.0)), COUNT(DISTINCT domain),
                   SUM(CASE WHEN {level_col}='L3' THEN 1 ELSE 0 END)
            FROM metrics_v02
            GROUP BY ts, series
            """
        ).fetchall()
    else:
        rows = cur.execute(
            """
            SELECT ts, series, AVG(COALESCE(W,0.0)), COUNT(DISTINCT domain), 0
            FROM metrics_v02
            GROUP BY ts, series
            """
        ).fetchall()
    for ts, s, avgw, doms, l3 in rows:
        sc = resolve_series(s)
        key = (ts, sc)
        if key not in wavg:
            wavg[key] = 0.0
            dom_count[key] = 0
            l3_count[key] = 0
        wavg[key] = max(wavg[key], float(avgw or 0.0))
        dom_count[key] += int(doms or 0)
        l3_count[key] += int(l3 or 0)

    prepare_tables(cur)

    series_ts_values = {s: [wavg.get((ts, s), 0.0) for ts in ts_list] for s in series_list}
    ts_day = {ts: parse_ymd(ts) for ts in ts_list}
    event_profile_at_ts = {}
    for ts in ts_list:
        asof_day = ts_day.get(ts)
        for s in series_list:
            event_profile_at_ts[(ts, s)] = build_event_profile(
                events_by_series.get(s, []),
                asof_day,
                cfg["half_life_days"],
            )

    for i in range(1, len(ts_list)):
        ts_now = ts_list[i]
        for src in series_list:
            src_vals = series_ts_values[src]
            d_src = src_vals[i] - src_vals[i - 1]
            if d_src <= 0:
                continue
            x = src_vals[max(0, i - K) : i]
            for dst in series_list:
                if dst == src:
                    continue
                dst_vals = series_ts_values[dst]
                y = dst_vals[max(0, i - K + 1) : i + 1]
                corr = pearson(x, y)
                if corr <= 0:
                    continue
                profile = event_profile_at_ts[(ts_now, src)]
                dst_profile = event_profile_at_ts[(ts_now, dst)]
                edge_level = merge_level(profile.level, dst_profile.level)
                base_score = corr * d_src
                boosted_score = base_score * profile.boost
                delta_boost = boosted_score - base_score
                if boosted_score < 1e-6:
                    continue
                cur.execute(
                    """
                    INSERT OR REPLACE INTO chain_edges_v10
                    (ts,src_series,dst_series,corr,dW_src,boost_multiplier,base_score,boosted_score,delta_boost,
                     push,push_raw,src_event_date,src_event_type,src_event_strength,src_event_decayed_strength,
                     max_event_level,src_matched_signals_json)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        ts_now,
                        src,
                        dst,
                        float(corr),
                        float(d_src),
                        float(profile.boost),
                        float(base_score),
                        float(boosted_score),
                        float(delta_boost),
                        float(boosted_score),
                        float(base_score),
                        profile.event_date,
                        profile.event_type,
                        float(profile.strength),
                        float(profile.decayed_strength),
                        edge_level,
                        profile.matched_signals_json,
                    ),
                )

        for dst in series_list:
            W = float(wavg.get((ts_now, dst), 0.0))
            incoming = cur.execute(
                """
                SELECT src_series,corr,base_score,boosted_score,delta_boost,max_event_level
                FROM chain_edges_v10
                WHERE ts=? AND dst_series=?
                ORDER BY boosted_score DESC
                """,
                (ts_now, dst),
            ).fetchall()

            inc_base = sum(float(r[2] or 0.0) for r in incoming)
            inc_boosted = sum(float(r[3] or 0.0) for r in incoming)
            inc_delta = sum(float(r[4] or 0.0) for r in incoming)
            W_proj = W + inc_boosted
            slot_key = ts_now[:13]
            forcing = float(E_DECAY.get(slot_key, {}).get(dst, 0.0))
            if DEBUG_EVENT_FORCING and forcing > 0:
                print("FORCING HIT", slot_key, dst, forcing)
            W_proj += forcing

            if incoming:
                top_src = incoming[0][0]
                share = float(incoming[0][1] or 0.0)
                top_push_boosted = float(incoming[0][3] or 0.0)
                top_push_base = float(incoming[0][2] or 0.0)
                max_event_level = str(incoming[0][5] or "L1")
            else:
                top_src = None
                share = 0.0
                top_push_boosted = 0.0
                top_push_base = 0.0
                max_event_level = "L1"

            uplift = W_proj - W
            chain_flag = 1 if (uplift >= 0.06 and top_push_boosted >= 0.5 * uplift) else 0
            status = "持續中" if (W_proj >= TH_SUS or W >= TH_SUS) else "平穩"
            doms = int(dom_count.get((ts_now, dst), 0))
            l3 = int(l3_count.get((ts_now, dst), 0))

            cur.execute(
                """
                INSERT OR REPLACE INTO series_chain_v10
                (ts,series,W_avg,W_proj,status,chain_flag,top_src,share,push,push_raw,base_push,boosted_push,delta_boost,domains,L3_domains,max_event_level)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    ts_now,
                    dst,
                    W,
                    W_proj,
                    status,
                    chain_flag,
                    top_src,
                    share,
                    top_push_boosted,
                    top_push_base,
                    inc_base,
                    inc_boosted,
                    inc_delta,
                    doms,
                    l3,
                    max_event_level,
                ),
            )

    if ts_list:
        latest_idx = len(ts_list) - 1
        latest_ts = ts_list[-1]
        latest_day = ts_day.get(latest_ts)
        ts_index = {ts: i for i, ts in enumerate(ts_list)}
        agg = {}
        rows = cur.execute(
            """
            SELECT ts, src_series, dst_series, corr, base_score, boosted_score, delta_boost
            FROM chain_edges_v10
            """
        ).fetchall()
        for ts, src, dst, corr, base_score, boosted_score, delta_boost in rows:
            idx = ts_index.get(ts, latest_idx)
            delta = max(0, latest_idx - idx)
            decay = math.exp(-delta / TAU)
            key = (dst, src)
            if key not in agg:
                agg[key] = [0.0, 0.0, 0.0, 0.0, 0]
            agg[key][0] += float(base_score or 0.0) * decay
            agg[key][1] += float(boosted_score or 0.0) * decay
            agg[key][2] += float(delta_boost or 0.0) * decay
            agg[key][3] += float(corr or 0.0)
            agg[key][4] += 1

        latest_profile = {
            s: build_event_profile(events_by_series.get(s, []), latest_day, cfg["half_life_days"])
            for s in series_list
        }

        for (dst, src), (base_sum, boosted_sum, delta_sum, corr_sum, n) in agg.items():
            share = corr_sum / n if n else 0.0
            profile = latest_profile.get(src, EventProfile("", "", 0.0, 0.0, 1.0, "L1", "[]"))
            boost_multiplier = boosted_sum / base_sum if base_sum > 1e-12 else 1.0
            cur.execute(
                """
                INSERT OR REPLACE INTO chain_edges_decay_latest
                (ts,src_series,dst_series,share,base_score,boosted_score,delta_boost,boost_multiplier,
                 push,push_raw,edge_n,src_event_date,src_event_type,src_event_strength,src_event_decayed_strength,
                 max_event_level,src_matched_signals_json)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    latest_ts,
                    src,
                    dst,
                    float(share),
                    float(base_sum),
                    float(boosted_sum),
                    float(delta_sum),
                    float(boost_multiplier),
                    float(boosted_sum),
                    float(base_sum),
                    int(n),
                    profile.event_date,
                    profile.event_type,
                    float(profile.strength),
                    float(profile.decayed_strength),
                    profile.level,
                    profile.matched_signals_json,
                ),
            )

        for dst in series_list:
            W = float(wavg.get((latest_ts, dst), 0.0))
            incoming = cur.execute(
                """
                SELECT src_series,share,base_score,boosted_score,delta_boost,max_event_level
                FROM chain_edges_decay_latest
                WHERE dst_series=?
                ORDER BY boosted_score DESC
                """,
                (dst,),
            ).fetchall()
            inc_base = sum(float(r[2] or 0.0) for r in incoming)
            inc_boosted = sum(float(r[3] or 0.0) for r in incoming)
            inc_delta = sum(float(r[4] or 0.0) for r in incoming)
            W_proj = W + inc_boosted
            slot_key = latest_ts[:13]
            forcing = float(E_DECAY.get(slot_key, {}).get(dst, 0.0))
            if DEBUG_EVENT_FORCING and forcing > 0:
                print("FORCING HIT", slot_key, dst, forcing)
            W_proj += forcing

            if incoming:
                top_src = incoming[0][0]
                share = float(incoming[0][1] or 0.0)
                top_push_base = float(incoming[0][2] or 0.0)
                top_push_boosted = float(incoming[0][3] or 0.0)
                max_event_level = str(incoming[0][5] or "L1")
            else:
                top_src = None
                share = 0.0
                top_push_base = 0.0
                top_push_boosted = 0.0
                max_event_level = "L1"

            uplift = W_proj - W
            chain_flag = 1 if (uplift >= 0.06 and top_push_boosted >= 0.5 * uplift) else 0
            status = "持續中" if (W_proj >= TH_SUS or W >= TH_SUS) else "平穩"
            doms = int(dom_count.get((latest_ts, dst), 0))
            l3 = int(l3_count.get((latest_ts, dst), 0))
            cur.execute(
                """
                INSERT OR REPLACE INTO series_chain_decay_latest
                (ts,series,W_avg,W_proj,status,chain_flag,top_src,share,push,push_raw,base_push,boosted_push,delta_boost,domains,L3_domains,max_event_level)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    latest_ts,
                    dst,
                    W,
                    W_proj,
                    status,
                    chain_flag,
                    top_src,
                    share,
                    top_push_boosted,
                    top_push_base,
                    inc_base,
                    inc_boosted,
                    inc_delta,
                    doms,
                    l3,
                    max_event_level,
                ),
            )

    con.commit()
    con.close()
    print(
        f"OK: built chain tables at {cfg['db_path']} "
        f"(half_life_days={cfg['half_life_days']})"
    )


if __name__ == "__main__":
    main()
