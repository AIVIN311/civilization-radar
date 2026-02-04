import json
import sqlite3
from collections import defaultdict

DB_PATH = "radar.db"
CFG_PATH = "chain_dynamics_v01.json"
OUT_PATH = "signals_chain_v01.json"

def load_cfg():
    with open(CFG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def fetch_latest_ts(cur):
    row = cur.execute("SELECT MAX(ts) FROM metrics_v02").fetchone()
    if not row or not row[0]:
        raise RuntimeError("No metrics_v02 found. Run: python upgrade_to_v02.py")
    return row[0]

def fetch_prev_ts(cur, latest_ts):
    row = cur.execute("SELECT MAX(ts) FROM metrics_v02 WHERE ts < ?", (latest_ts,)).fetchone()
    return row[0] if row and row[0] else None

def fetch_series_map(cur, ts):
    # v02_series_latest：每個 ts 一列 series 指標
    rows = cur.execute("""
        SELECT series, heat_avg, A_avg, D_avg, W_avg
        FROM v02_series_latest
        WHERE ts = ?
    """, (ts,)).fetchall()
    m = {}
    for series, heat, A, D, W in rows:
        m[series] = {
            "heat": float(heat or 0.0),
            "A": float(A or 0.0),
            "D": float(D or 0.0),
            "W": float(W or 0.0),
        }
    return m

def activate_over_bg(W, bg):
    return max(0.0, float(W) - float(bg))

def main():
    cfg = load_cfg()
    th_bg = cfg["thresholds"]["bg"]
    decay = cfg["push_model"].get("decay", 0.85)
    use_delta_w = cfg["push_model"].get("use_delta_w", True)
    min_share = cfg["push_model"].get("min_share_to_call_chain", 0.55)

    edges = cfg["edges"]
    nodes = cfg["series_nodes"]

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    latest_ts = fetch_latest_ts(cur)
    prev_ts = fetch_prev_ts(cur, latest_ts)

    latest = fetch_series_map(cur, latest_ts)
    prev = fetch_series_map(cur, prev_ts) if prev_ts else {}

    # 基礎完整性檢查：若某些 series 不在 DB，先補 0
    for s in nodes:
        latest.setdefault(s, {"heat":0.0,"A":0.0,"D":0.0,"W":0.0})
        prev.setdefault(s, {"heat":0.0,"A":0.0,"D":0.0,"W":0.0})

    # 計算 series 的 ΔW（可換成 slope/rolling，先用 diff）
    deltaW = {}
    for s in nodes:
        deltaW[s] = latest[s]["W"] - prev[s]["W"]

    # 依 edge 計算 push：Push = activation(W) * max(0, ΔW) * weight
    # 這裡把 ΔW 當「加速度」，只吃正向（升溫）以避免雜訊反向震盪
    inflow = defaultdict(float)         # dst -> total external push
    contrib = defaultdict(lambda: defaultdict(float))  # dst -> src -> push

    for e in edges:
        src, dst, w, lag = e["src"], e["dst"], float(e["w"]), int(e.get("lag", 1))

        srcW = latest[src]["W"]
        act = activate_over_bg(srcW, th_bg)

        dW = deltaW[src] if use_delta_w else 1.0
        accel = max(0.0, dW)

        push = act * accel * w
        # lag 先不做跨 slot 回放（工程上可擴充），v1.0 先當「預測推力」
        inflow[dst] += push
        contrib[dst][src] += push

    # 做一個「壓力分解」：base(W) + external_push(經衰減) = projected_pressure
    # external push 先乘 decay，避免一個 slot 推爆一切
    out = {
        "version": cfg["version"],
        "ts": latest_ts,
        "prev_ts": prev_ts,
        "thresholds": cfg["thresholds"],
        "series": {}
    }

    for s in nodes:
        baseW = latest[s]["W"]
        ext = inflow.get(s, 0.0) * decay
        proj = baseW + ext

        # 找最大來源與占比（用來判斷「鏈式」）
        src_map = contrib.get(s, {})
        total = sum(src_map.values()) or 0.0
        top_src, top_val, top_share = None, 0.0, 0.0
        if total > 0:
            top_src = max(src_map, key=lambda k: src_map[k])
            top_val = src_map[top_src]
            top_share = top_val / total

        out["series"][s] = {
            "W_base": round(baseW, 6),
            "dW": round(deltaW[s], 6),
            "push_in": round(inflow.get(s, 0.0), 6),
            "push_in_decay": round(ext, 6),
            "W_projected": round(proj, 6),
            "top_src": top_src,
            "top_src_share": round(top_share, 6),
            "is_chain_driven": bool(top_share >= min_share and total > 0.0),
            "contributors": {k: round(v, 6) for k, v in sorted(src_map.items(), key=lambda kv: kv[1], reverse=True)}
        }

    con.close()

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"Wrote {OUT_PATH} (chain inflow + projected pressure)")

if __name__ == "__main__":
    main()
