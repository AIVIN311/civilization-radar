import os
import json
import sqlite3
import math

DB_PATH = "radar.db"
K = 16  # window size, align with dashboard sparkline
TH_BG = 1.20
TH_SUS = 1.80
TAU = 12.0  # push decay time constant (slots)
EVENT_FORCING_PATH = "event_forcing_v0.2.json"
DEBUG_EVENT_FORCING = False

# load event forcing once
E_DECAY = {}
if os.path.exists(EVENT_FORCING_PATH):
    try:
        with open(EVENT_FORCING_PATH, "r", encoding="utf-8") as f:
            payload = json.load(f)
        E_DECAY = payload.get("E_decay", {}) or {}
    except Exception:
        E_DECAY = {}

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

def main():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    # --- basic checks ---
    latest = cur.execute("SELECT MAX(ts) FROM metrics_v02").fetchone()[0]
    if not latest:
        raise SystemExit("FATAL: metrics_v02 empty. Run upgrade_to_v02.py first.")

    level_col = detect_level_col(cur)

    # --- build series timeline: ts x series -> W_avg ---
    ts_list = [r[0] for r in cur.execute("SELECT DISTINCT ts FROM metrics_v02 ORDER BY ts").fetchall()]
    series_list = [r[0] for r in cur.execute("SELECT DISTINCT series FROM metrics_v02 ORDER BY series").fetchall()]

    # W_avg map: (ts, series) -> float
    wavg = {}
    dom_count = {}
    l3_count = {}

    # domains + L3 counts (from metrics_v02 if it has level; else L3=0)
    if level_col:
        rows = cur.execute(f"""
            SELECT ts, series,
                   AVG(COALESCE(W,0.0)) AS wavg,
                   COUNT(DISTINCT domain) AS doms,
                   SUM(CASE WHEN {level_col}='L3' THEN 1 ELSE 0 END) AS l3
            FROM metrics_v02
            GROUP BY ts, series
        """).fetchall()
    else:
        rows = cur.execute("""
            SELECT ts, series,
                   AVG(COALESCE(W,0.0)) AS wavg,
                   COUNT(DISTINCT domain) AS doms
            FROM metrics_v02
            GROUP BY ts, series
        """).fetchall()

    for r in rows:
        ts = r[0]
        s = r[1]
        wavg[(ts, s)] = float(r[2] or 0.0)
        dom_count[(ts, s)] = int(r[3] or 0)
        if level_col:
            l3_count[(ts, s)] = int(r[4] or 0)
        else:
            l3_count[(ts, s)] = 0

    # --- prepare output tables ---
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS chain_edges_v10 (
      ts TEXT NOT NULL,
      src_series TEXT NOT NULL,
      dst_series TEXT NOT NULL,
      corr REAL NOT NULL,
      push REAL NOT NULL,
      PRIMARY KEY (ts, src_series, dst_series)
    );

    CREATE TABLE IF NOT EXISTS chain_edges_decay_latest (
      ts TEXT NOT NULL,
      src_series TEXT NOT NULL,
      dst_series TEXT NOT NULL,
      share REAL NOT NULL,
      push REAL NOT NULL,
      push_raw REAL NOT NULL,
      edge_n INTEGER NOT NULL,
      PRIMARY KEY (src_series, dst_series)
    );

    CREATE TABLE IF NOT EXISTS series_chain_v10 (
      ts TEXT NOT NULL,
      series TEXT NOT NULL,
      W_avg REAL NOT NULL,
      W_proj REAL NOT NULL,
      status TEXT NOT NULL,
      chain_flag INTEGER NOT NULL,
      top_src TEXT,
      share REAL NOT NULL,
      push REAL NOT NULL,
      domains INTEGER NOT NULL,
      L3_domains INTEGER NOT NULL,
      PRIMARY KEY (ts, series)
    );

    CREATE TABLE IF NOT EXISTS series_chain_decay_latest (
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
      domains INTEGER NOT NULL,
      L3_domains INTEGER NOT NULL,
      PRIMARY KEY (ts, series)
    );

    CREATE INDEX IF NOT EXISTS idx_edges_ts_dst ON chain_edges_v10(ts, dst_series);
    CREATE INDEX IF NOT EXISTS idx_series_ts ON series_chain_v10(ts);
    """)

    # overwrite-recompute (safe for iterative dev)
    cur.execute("DELETE FROM chain_edges_v10")
    cur.execute("DELETE FROM chain_edges_decay_latest")
    cur.execute("DELETE FROM series_chain_v10")
    cur.execute("DELETE FROM series_chain_decay_latest")

    # --- build per-series time arrays aligned to ts_list ---
    series_ts_values = {s: [wavg.get((ts, s), 0.0) for ts in ts_list] for s in series_list}

    # --- compute for each ts index i>=1 ---
    for i in range(1, len(ts_list)):
        ts_now = ts_list[i]
        # windows: src uses up to i-1, dst uses up to i (lag1)
        for src in series_list:
            src_vals = series_ts_values[src]
            d_src = src_vals[i] - src_vals[i - 1]
            if d_src <= 0:
                continue  # only positive push when src is heating up

            x = src_vals[max(0, i - K):i]  # end at i-1
            for dst in series_list:
                if dst == src:
                    continue
                dst_vals = series_ts_values[dst]
                y = dst_vals[max(0, i - K + 1):i + 1]  # end at i
                corr = pearson(x, y)
                if corr <= 0:
                    continue
                push = corr * d_src
                # tiny pushes are noise
                if push < 1e-6:
                    continue
                cur.execute(
                    "INSERT OR REPLACE INTO chain_edges_v10(ts,src_series,dst_series,corr,push) VALUES (?,?,?,?,?)",
                    (ts_now, src, dst, float(corr), float(push)),
                )

        # build series_chain_v10 rows for this ts
        for dst in series_list:
            W = float(wavg.get((ts_now, dst), 0.0))

            incoming = cur.execute("""
                SELECT src_series, corr, push
                FROM chain_edges_v10
                WHERE ts=? AND dst_series=?
                ORDER BY push DESC
            """, (ts_now, dst)).fetchall()

            inc_sum = sum(float(r[2] or 0.0) for r in incoming)
            W_proj = W + inc_sum
            slot_key = ts_now[:13]
            forcing = float(E_DECAY.get(slot_key, {}).get(dst, 0.0))
            if DEBUG_EVENT_FORCING and forcing > 0:
                print("FORCING HIT", slot_key, dst, forcing)
            W_proj += forcing

            # top src
            if incoming:
                top_src = incoming[0][0]
                share = float(incoming[0][1] or 0.0)
                top_push = float(incoming[0][2] or 0.0)
            else:
                top_src = None
                share = 0.0
                top_push = 0.0

            uplift = W_proj - W  # >=0 by construction
            # chain_flag: 外力是主要推手（可調門檻）
            chain_flag = 1 if (uplift >= 0.06 and top_push >= 0.5 * uplift) else 0

            # status: 與你截圖一致的粗分（持續中/平穩）
            status = "持續中" if (W_proj >= TH_SUS or W >= TH_SUS) else "平穩"

            doms = int(dom_count.get((ts_now, dst), 0))
            l3 = int(l3_count.get((ts_now, dst), 0))

            cur.execute("""
                INSERT OR REPLACE INTO series_chain_v10
                (ts,series,W_avg,W_proj,status,chain_flag,top_src,share,push,domains,L3_domains)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """, (ts_now, dst, W, W_proj, status, chain_flag, top_src, share, top_push, doms, l3))

    # --- build decayed latest aggregates ---
    if ts_list:
        latest_idx = len(ts_list) - 1
        latest_ts = ts_list[-1]
        ts_index = {ts: i for i, ts in enumerate(ts_list)}

        agg = {}
        rows = cur.execute("""
            SELECT ts, src_series, dst_series, corr, push
            FROM chain_edges_v10
        """).fetchall()
        for ts, src, dst, corr, push in rows:
            idx = ts_index.get(ts, latest_idx)
            delta = max(0, latest_idx - idx)
            decay = math.exp(-delta / TAU)
            push_val = float(push or 0.0)
            push_decay = push_val * decay
            key = (dst, src)
            if key not in agg:
                agg[key] = [0.0, 0.0, 0.0, 0]
            agg[key][0] += push_decay
            agg[key][1] += push_val
            agg[key][2] += float(corr or 0.0)
            agg[key][3] += 1

        for (dst, src), (push_decay_sum, push_raw_sum, corr_sum, n) in agg.items():
            share = (corr_sum / n) if n else 0.0
            cur.execute(
                """
                INSERT OR REPLACE INTO chain_edges_decay_latest
                (ts,src_series,dst_series,share,push,push_raw,edge_n)
                VALUES (?,?,?,?,?,?,?)
                """,
                (latest_ts, src, dst, float(share), float(push_decay_sum), float(push_raw_sum), int(n)),
            )

        for dst in series_list:
            W = float(wavg.get((latest_ts, dst), 0.0))
            incoming = cur.execute("""
                SELECT src_series, share, push, push_raw
                FROM chain_edges_decay_latest
                WHERE dst_series=?
                ORDER BY push DESC
            """, (dst,)).fetchall()

            inc_sum = sum(float(r[2] or 0.0) for r in incoming)
            W_proj = W + inc_sum
            slot_key = latest_ts[:13]
            forcing = float(E_DECAY.get(slot_key, {}).get(dst, 0.0))
            if DEBUG_EVENT_FORCING and forcing > 0:
                print("FORCING HIT", slot_key, dst, forcing)
            W_proj += forcing

            if incoming:
                top_src = incoming[0][0]
                share = float(incoming[0][1] or 0.0)
                top_push = float(incoming[0][2] or 0.0)
                top_push_raw = float(incoming[0][3] or 0.0)
            else:
                top_src = None
                share = 0.0
                top_push = 0.0
                top_push_raw = 0.0

            uplift = W_proj - W
            chain_flag = 1 if (uplift >= 0.06 and top_push >= 0.5 * uplift) else 0
            status = "持續中" if (W_proj >= TH_SUS or W >= TH_SUS) else "平穩"

            doms = int(dom_count.get((latest_ts, dst), 0))
            l3 = int(l3_count.get((latest_ts, dst), 0))

            cur.execute("""
                INSERT OR REPLACE INTO series_chain_decay_latest
                (ts,series,W_avg,W_proj,status,chain_flag,top_src,share,push,push_raw,domains,L3_domains)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """, (latest_ts, dst, W, W_proj, status, chain_flag, top_src, share, top_push, top_push_raw, doms, l3))

    con.commit()
    con.close()
    print("OK: built chain_edges_v10 + series_chain_v10")

if __name__ == "__main__":
    main()
