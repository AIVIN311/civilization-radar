import re
import sqlite3
import math
from html import escape
import sys
sys.path.append(".")
from src.load_events_derived import load_events_derived
import json

DB_PATH = "radar.db"
OUT_HTML = "dashboard_v02.html"

# ======= thresholds (v0.3) =======
TH_BG = 1.20     # 背景/可疑 (W for series status)
TH_SUS = 1.80    # 可疑/警戒 (W for series status)
TH_ALR = 2.30    # 警戒/事件 (W for series status)

A_BG = 1.0
A_SUS = 2.0
A_ALR = 3.0

SPARK_K = 16


def event_boost(max_strength: float) -> float:
    """
    strength(0~10) -> chain boost multiplier.
    v1.1: 1 + log1p(s)/2  (caps naturally, ~2.3 at s=10)
    """
    try:
        s = float(max_strength or 0.0)
    except Exception:
        s = 0.0
    if s <= 0:
        return 1.0
    return 1.0 + math.log1p(s) / 2.0


# ---------- helpers ----------
def table_or_view_exists(cur, name: str) -> bool:
    row = cur.execute(
        "SELECT 1 FROM sqlite_master WHERE (type='table' OR type='view') AND name=? LIMIT 1",
        (name,),
    ).fetchone()
    return bool(row)


def columns_of(cur, table_name: str):
    cols = cur.execute(f"PRAGMA table_info({table_name})").fetchall()
    # PRAGMA table_info returns: cid, name, type, notnull, dflt_value, pk
    return [c[1] for c in cols]


def risk_bucket(A):
    a = float(A or 0.0)
    if a >= A_ALR:
        return "r-red", "事件"
    if a >= A_SUS:
        return "r-orange", "警戒"
    if a >= A_BG:
        return "r-yellow", "可疑"
    return "r-green", "背景"


def arrow(d):
    d = float(d or 0.0)
    if d > 0.10:
        return "↑", "up"
    if d < -0.10:
        return "↓", "down"
    return "→", "flat"


def svg_spark(vs, w=140, h=22, p=2):
    if not vs:
        return "<span class='muted'>—</span>"

    vs = [float(x or 0.0) for x in vs]
    mn, mx = min(vs), max(vs)
    if mx - mn < 1e-9:
        mx += 1e-9

    pts = []
    for i, v in enumerate(vs):
        x = p + (w - 2 * p) * i / max(1, len(vs) - 1)
        y = p + (h - 2 * p) * (1 - (v - mn) / (mx - mn))
        pts.append(f"{x:.1f},{y:.1f}")

    lastx, lasty = pts[-1].split(",")
    return f"""
    <svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" aria-label="W sparkline">
      <polyline points="{' '.join(pts)}" fill="none" stroke="currentColor" stroke-width="1.6"/>
      <circle cx="{lastx}" cy="{lasty}" r="2" fill="currentColor"/>
    </svg>
    """


def safe_id(raw: str) -> str:
    sid = re.sub(r"[^0-9A-Za-z]+", "_", str(raw or "")).strip("_")
    return sid or "series"


def preview_domains(domains_csv: str, limit: int = 4) -> str:
    if not domains_csv:
        return "—"
    parts = [p.strip() for p in str(domains_csv).split(",") if p.strip()]
    if not parts:
        return "—"
    shown = ", ".join(parts[:limit])
    if len(parts) > limit:
        shown += f" (+{len(parts) - limit})"
    return shown


def fetch_topk_edges_latest(cur, topk: int = 3):
    if not table_or_view_exists(cur, "v03_chain_edges_latest"):
        return {}

    cols = columns_of(cur, "v03_chain_edges_latest")
    if "dst_series" not in cols or "src_series" not in cols:
        return {}

    share_col = "share" if "share" in cols else ("corr" if "corr" in cols else None)
    push_col = "push" if "push" in cols else None
    push_raw_col = "push_raw" if "push_raw" in cols else None
    domain_col = "domain" if "domain" in cols else None

    share_expr = share_col if share_col else "0.0"
    push_expr = push_col if push_col else "0.0"
    push_raw_expr = push_raw_col if push_raw_col else "0.0"
    domain_expr = domain_col if domain_col else "''"

    sql = f"""
    WITH agg AS (
      SELECT
        dst_series,
        src_series,
        SUM({share_expr}) AS share_sum,
        SUM({push_expr}) AS push_sum,
        SUM({push_raw_expr}) AS push_raw_sum,
        COUNT(*) AS edge_n,
        GROUP_CONCAT({domain_expr}, ', ') AS domains_csv
      FROM v03_chain_edges_latest
      GROUP BY dst_series, src_series
    ),
    ranked AS (
      SELECT
        dst_series, src_series, share_sum, push_sum, push_raw_sum, edge_n, domains_csv,
        ROW_NUMBER() OVER (PARTITION BY dst_series ORDER BY push_sum DESC) AS rn
      FROM agg
    )
    SELECT dst_series, src_series, share_sum, push_sum, push_raw_sum, edge_n, COALESCE(domains_csv, '') AS domains_csv
    FROM ranked
    WHERE rn <= ?
    ORDER BY dst_series, rn
    """

    rows = cur.execute(sql, (topk,)).fetchall()
    out = {}
    for dst, src, share_sum, push_sum, push_raw_sum, edge_n, domains_csv in rows:
        out.setdefault(dst, []).append(
            {
                "src_series": src,
                "share_sum": float(share_sum or 0.0),
                "push_sum": float(push_sum or 0.0),
                "push_raw": float(push_raw_sum or 0.0) if push_raw_col else None,
                "edge_n": int(edge_n or 0),
                "domains_csv": domains_csv or "",
            }
        )
    return out


def main():
    # ✅ load REAL derived events (from daily snapshots)
    # domain_lower -> list[events]
    events_real = load_events_derived("output/events_derived.jsonl")

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    latest = cur.execute("SELECT MAX(ts) FROM metrics_v02").fetchone()[0]
    if not latest:
        raise SystemExit("FATAL: metrics_v02 is empty. Run: python upgrade_to_v02.py")

    prev = cur.execute("SELECT MAX(ts) FROM metrics_v02 WHERE ts < ?", (latest,)).fetchone()[0]

    # ---------- domain latest (with optional columns) ----------
    if not table_or_view_exists(cur, "v02_domain_latest"):
        raise SystemExit("FATAL: view v02_domain_latest not found. Run: python upgrade_to_v02.py")

    dcols = columns_of(cur, "v02_domain_latest")
    has_chain_flag = "chain_flag" in dcols
    has_projected = "projected" in dcols or "W_proj" in dcols or "projected_W" in dcols

    # decide projected column name (best-effort)
    projected_col = None
    for cand in ["projected", "projected_W", "W_proj"]:
        if cand in dcols:
            projected_col = cand
            break

    select_cols = [
        "domain", "series", "req", "level_max", "heat", "A", "D", "W", "matched_json", "sig"
    ]
    if has_chain_flag:
        select_cols.append("chain_flag")
    if projected_col:
        select_cols.append(projected_col)

    domains = cur.execute(f"""
        SELECT {",".join(select_cols)}
        FROM v02_domain_latest
        ORDER BY W DESC, heat DESC
    """).fetchall()

    # prev W map for Δ
    prevW = {}
    if prev:
        for d, w in cur.execute("SELECT domain, W FROM metrics_v02 WHERE ts=?", (prev,)).fetchall():
            prevW[d] = float(w or 0.0)

    # spark ts list
    ts = [r[0] for r in cur.execute("""
        SELECT DISTINCT ts
        FROM metrics_v02
        WHERE ts<=?
        ORDER BY ts DESC
        LIMIT ?
    """, (latest, SPARK_K)).fetchall()][::-1]

    spark = {}
    if ts:
        q = ",".join("?" * len(ts))
        rows = cur.execute(
            f"SELECT ts, domain, W FROM metrics_v02 WHERE ts IN ({q}) ORDER BY ts ASC",
            ts,
        ).fetchall()
        for t, d, w in rows:
            spark.setdefault(d, {})[t] = float(w or 0.0)
        for d in list(spark.keys()):
            spark[d] = [spark[d].get(t, 0.0) for t in ts]

    # ---------- series (prefer chain view if exists) ----------
    chain_loaded = False
    series_rows = []

    series_candidates = [
        "v03_series_chain_latest",   # recommended for chain v1.0
        "v02_series_chain_latest",   # alternative
        "v02_series_latest",         # fallback (no chain)
    ]

    chosen = None
    for v in series_candidates:
        if table_or_view_exists(cur, v):
            chosen = v
            break

    topk_edges = {}
    if chosen in ("v03_series_chain_latest", "v02_series_chain_latest"):
        chain_loaded = True
        scol = columns_of(cur, chosen)
        want = ["series", "W_avg", "W_proj", "status", "chain_flag", "top_src", "share", "push", "push_raw", "domains", "L3_domains"]
        got = [c for c in want if c in scol]

        if "ts" in scol:
            series_rows = cur.execute(
                f"SELECT {','.join(got)} FROM {chosen} WHERE ts=? ORDER BY W_proj DESC, W_avg DESC",
                (latest,),
            ).fetchall()
        else:
            series_rows = cur.execute(
                f"SELECT {','.join(got)} FROM {chosen} ORDER BY W_proj DESC, W_avg DESC"
            ).fetchall()

        topk_edges = fetch_topk_edges_latest(cur, topk=3)

    else:
        chosen = "v02_series_latest"
        scol = columns_of(cur, chosen)
        if "ts" in scol:
            series_rows = cur.execute("""
                SELECT series, domains, L3_domains, W_avg
                FROM v02_series_latest
                WHERE ts=?
                ORDER BY W_avg DESC
            """, (latest,)).fetchall()
        else:
            series_rows = cur.execute("""
                SELECT series, domains, L3_domains, W_avg
                FROM v02_series_latest
                ORDER BY W_avg DESC
            """).fetchall()

    event_latest = {}
    if table_or_view_exists(cur, "events_v01"):
        erows = cur.execute("""
            WITH latest AS (
              SELECT domain, MAX(date) AS max_date
              FROM events_v01
              GROUP BY domain
            ),
            picked AS (
              SELECT
                e.domain,
                e.event_type,
                e.req_key,
                e.strength,
                ROW_NUMBER() OVER (
                  PARTITION BY e.domain
                  ORDER BY e.date DESC, e.id DESC
                ) AS rn
              FROM events_v01 e
              JOIN latest l
                ON l.domain = e.domain
               AND l.max_date = e.date
            )
            SELECT domain, event_type, req_key, strength
            FROM picked
            WHERE rn = 1
        """).fetchall()
        for domain, event_type, req_key, strength in erows:
            dk = str(domain or "").lower()
            if not dk:
                continue
            event_latest[dk] = {
                "event_type": str(event_type or "unknown"),
                "req_key": str(req_key or "dns_total"),
                "strength": float(strength or 0.0),
            }

    # latest events date: series -> max strength (for top-3 explainability)
    event_strength_max = {}
    try:
        latest_event_date = cur.execute("SELECT MAX(date) FROM events_v01").fetchone()[0]
        if latest_event_date:
            rows_ev = cur.execute("""
                SELECT series, MAX(strength) AS max_strength
                FROM events_v01
                WHERE date = ?
                GROUP BY series
            """, (latest_event_date,)).fetchall()
            for s, mx in rows_ev:
                event_strength_max[str(s)] = float(mx or 0.0)
    except Exception:
        event_strength_max = {}

    con.close()

    # ---------- render ----------
    title = "文明雷達 v0.3（鏈式戰情）" if chain_loaded else "文明雷達 v0.2（戰情中心）"

    html = []
    html.append("<!doctype html><html><head><meta charset=utf-8>")
    html.append("<meta name=viewport content='width=device-width,initial-scale=1'>")
    html.append(f"<title>{escape(title)}</title>")

    html.append("""
<style>
body{font-family:system-ui,-apple-system,Segoe UI,sans-serif;margin:0;background:#fff;color:#111}
main{max-width:1280px;margin:auto;padding:24px 18px}
h1{margin:0 0 8px;font-size:28px}
.meta{color:#666;margin-bottom:14px;line-height:1.55}

.controls{display:flex;gap:10px;flex-wrap:wrap;margin:12px 0 14px}
button{border:1px solid #ddd;background:#fff;padding:6px 10px;border-radius:10px;cursor:pointer}
button.active{background:#111;color:#fff;border-color:#111}
input{padding:6px 10px;border:1px solid #ddd;border-radius:10px;min-width:260px}

.grid{display:grid;grid-template-columns:1.75fr 1fr;gap:16px;align-items:start}
.card{border:1px solid #eee;border-radius:14px;padding:14px;background:#fff}

table{width:100%;border-collapse:collapse}
th,td{padding:10px 8px;border-bottom:1px solid #f1f1f1;font-size:14px;vertical-align:top}
th{color:#666;font-weight:650;text-align:left;font-size:13px}
small{color:#666}
a{color:#111;text-decoration:none}
a:hover{text-decoration:underline}

.badge{display:inline-block;padding:2px 8px;border:1px solid #eee;border-radius:999px;font-size:12px;color:#444;background:#fff}
.badge.black{background:#111;color:#fff;border-color:#111}
.muted{color:#888}

.spark{color:#111}
.delta{font-size:12px;padding:2px 6px;border-radius:8px;border:1px solid #eee;display:inline-block}
.delta.up{color:#0b6}
.delta.down{color:#c33}
.delta.flat{color:#777}

.dot{width:10px;height:10px;border-radius:50%;display:inline-block}
.r-red{background:#ef4444}
.r-orange{background:#f97316}
.r-yellow{background:#f0b429}
.r-green{background:#18a058}

.lv{font-weight:800}
.lv.L3{color:#b91c1c}
.lv.L2{color:#c2410c}
.lv.L1{color:#444}

.match{cursor:pointer;color:#2563eb}
.matchbox{display:none;color:#555;font-size:12px;margin-top:6px;line-height:1.45;white-space:pre-wrap}

.right h3{margin:4px 0 10px}
.hint{color:#666;font-size:12px;line-height:1.5;margin-top:10px}
.pill{display:inline-block;border:1px solid #eee;border-radius:999px;padding:6px 10px;font-size:12px;color:#444;margin:6px 6px 0 0}
.status{display:inline-flex;align-items:center;gap:6px}
.sdot{width:8px;height:8px;border-radius:50%;display:inline-block;background:#9ca3af}
.sdot.on{background:#f97316}
.series-controls{display:flex;gap:10px;flex-wrap:wrap;margin:8px 0 10px}
.top3-row{display:none;background:#fafafa}
.top3-box{font-size:12px;color:#444;line-height:1.6}
.top3-table{width:100%;border-collapse:collapse}
.top3-table th,.top3-table td{padding:6px 8px;border-bottom:1px solid #eee;font-size:12px}
</style>
""")

    html.append("</head><body><main>")
    html.append(f"<h1>{escape(title)}</h1>")
    html.append(
        f"<div class=meta>"
        f"最新時段：{escape(str(latest))} · sparkline 回看 {SPARK_K} slots<br>"
        f"門檻（A 自適應）：背景&lt;{A_BG:.1f}，可疑≥{A_BG:.1f}，警戒≥{A_SUS:.1f}，事件≥{A_ALR:.1f}<br>"
        f"鏈式資料：{'已載入' if chain_loaded else '未載入（目前使用 v02_series_latest）'} · "
        f"derived_events：{'已載入' if events_real else '未載入'}"
        f"</div>"
    )

    html.append("""
<div class=controls>
  <button data-mode="all" class=active>全部</button>
  <button data-mode="event">事件</button>
  <button data-mode="alert">事件＋警戒</button>
  <button data-mode="sus">可疑以上</button>
  <button data-mode="l3">只看 L3</button>
  <button data-mode="chain">只看鏈式</button>
  <input id=search placeholder="搜尋 domain / series / sig">
</div>
""")

    html.append("<div class=grid>")

    # ===== left: domain table =====
    html.append("<div class='card left'>")
    html.append("<h3 style='margin:4px 0 10px'>領域預警榜</h3>")
    html.append("<table id=domainTable><thead><tr>")
    html.append("<th></th><th>Domain</th><th>Series</th><th>Level</th><th>A</th><th>W</th><th>Δ</th><th>Spark</th><th>Event</th><th>Matched</th><th>Sig</th>")
    if projected_col:
        html.append("<th>Projected</th>")
    html.append("</tr></thead><tbody>")

    for row in domains:
        idx = 0
        domain = row[idx]; idx += 1
        series = row[idx]; idx += 1
        req = row[idx]; idx += 1
        lv = row[idx]; idx += 1
        heat = row[idx]; idx += 1
        A = row[idx]; idx += 1
        Dv = row[idx]; idx += 1
        W = row[idx]; idx += 1
        matched = row[idx]; idx += 1
        sig = row[idx]; idx += 1

        chain_flag = None
        if has_chain_flag:
            chain_flag = row[idx]; idx += 1

        projected_val = None
        if projected_col:
            projected_val = row[idx]; idx += 1

        # ---- Δ and spark (keep from DB)
        Wv = float(W or 0.0)
        prevw = float(prevW.get(domain, Wv))
        dw = Wv - prevw
        arr, cls = arrow(dw)
        sp = svg_spark(spark.get(domain, []))

        # ---- ✅ REAL derived events override (A / label / sig / matched)
        dom_l = str(domain).lower()
        real_list = events_real.get(dom_l, [])

        Av = float(A or 0.0)
        if real_list:
            last_ev = real_list[-1]
            # ratio=1.0 means +100% vs baseline (2x)
            Av = float(last_ev.get("ratio") or 0.0)
            sig = "dns_spike(real)"
            matched = json.dumps(["dns_spike"], ensure_ascii=False)

        color, label = risk_bucket(Av)
        latest_ev = event_latest.get(dom_l)
        if latest_ev:
            event_text = f"{latest_ev['event_type']} | s={latest_ev['strength']:.1f} | {latest_ev['req_key']}"
        else:
            event_text = "—"

        # chain badge rendering (domain-level)
        chain_badge = ""
        chain_yes = False
        if has_chain_flag:
            chain_yes = str(chain_flag).lower() in ("1", "true", "yes", "y")
            if chain_yes:
                chain_badge = " <span class='badge black'>CHAIN</span>"

        # link
        d_esc = escape(str(domain))
        s_esc = escape(str(series or "unknown"))
        sig_esc = escape(str(sig or "—"))
        m_esc = escape(str(matched or ""))

        l3_badge = " <span class='badge'>L3</span>" if str(lv or "").upper() == "L3" else ""
        html.append(
            f"<tr data-risk='{escape(label)}' data-level='{escape(str(lv or 'L1'))}' data-chain='{1 if chain_yes else 0}' "
            f"data-text='{escape(str(domain))} {escape(str(series or ''))} {escape(str(sig or ''))} {escape(event_text)}'>"
            f"<td><span class='dot {color}'></span></td>"
            f"<td><a href='https://{d_esc}/' target='_blank' rel='noopener noreferrer'>{d_esc}</a></td>"
            f"<td>{s_esc}{chain_badge}</td>"
            f"<td>{escape(label)}{l3_badge}</td>"
            f"<td><small>{Av:.2f}</small></td>"
            f"<td><b>{Wv:.3f}</b></td>"
            f"<td><span class='delta {cls}'>{arr} {dw:+.3f}</span></td>"
            f"<td class='spark'>{sp}</td>"
            f"<td><span class='badge'>{escape(event_text)}</span></td>"
            f"<td><span class='match'>展開</span><div class='matchbox'>{m_esc}</div></td>"
            f"<td><span class='badge'>{sig_esc}</span></td>"
        )

        if projected_col:
            try:
                pv = float(projected_val or 0.0)
                html.append(f"<td>{pv:.3f}</td>")
            except Exception:
                html.append(f"<td>{escape(str(projected_val))}</td>")

        html.append("</tr>")

    html.append("</tbody></table></div>")

    # ===== right: series table =====
    html.append("<div class='card right'>")
    html.append("<h3>系列戰情（含 projected / chain）</h3>")

    if chain_loaded:
        html.append("""
<div class=series-controls>
  <button id=stormToggle>風暴模式</button>
</div>
""")
        html.append("<table><thead><tr>"
                    "<th>Series</th><th>W_avg</th><th>W_proj</th><th>狀態</th><th>Chain</th><th>Top src</th>"
                    "<th>share</th><th>base_score</th><th>boosted_score</th><th>domains</th><th>L3</th><th>Top-3</th>"
                    "</tr></thead><tbody>")

        for r in series_rows:
            idxm = {name: i for i, name in enumerate(got)}
            series = r[idxm["series"]] if "series" in idxm else "—"
            W_avg = r[idxm["W_avg"]] if "W_avg" in idxm else 0.0
            W_proj = r[idxm["W_proj"]] if "W_proj" in idxm else W_avg
            status = r[idxm["status"]] if "status" in idxm else ""
            chain_flag = r[idxm["chain_flag"]] if "chain_flag" in idxm else 0
            top_src = r[idxm["top_src"]] if "top_src" in idxm else "—"
            share = r[idxm["share"]] if "share" in idxm else 0.0
            push = r[idxm["push"]] if "push" in idxm else 0.0
            push_raw = r[idxm["push_raw"]] if "push_raw" in idxm else None
            doms = r[idxm["domains"]] if "domains" in idxm else 0
            l3 = r[idxm["L3_domains"]] if "L3_domains" in idxm else 0

            try:
                wa = float(W_avg or 0.0)
                wp = float(W_proj or 0.0)
                if not status:
                    status = "持續中" if wp >= TH_SUS else "平穩"
            except Exception:
                wa, wp = W_avg, W_proj

            chain_yes = str(chain_flag).lower() in ("1", "true", "yes", "y")
            sdot = "sdot on" if (float(W_proj or 0.0) - float(W_avg or 0.0)) > 0.06 else "sdot"

            chain_badge = "<span class='badge black'>YES</span>" if chain_yes else "<span class='muted'>no</span>"
            push_val = float(push or 0.0)
            dst_boost = event_boost(float(event_strength_max.get(str(series), 0.0) or 0.0))
            base_score = (push_val / dst_boost) if dst_boost > 0 else push_val
            series_id = safe_id(series)
            top3_id = f"top3_{series_id}"

            html.append(
                f"<tr class='series-row' data-chain='{'YES' if chain_yes else 'no'}' data-push='{push_val:.4f}'>"
            )
            html.append(f"<td><b>{escape(str(series))}</b></td>")
            html.append(f"<td>{float(W_avg or 0.0):.3f}</td>")
            html.append(f"<td><b>{float(W_proj or 0.0):.3f}</b></td>")
            html.append(f"<td><span class='status'><span class='{sdot}'></span>{escape(str(status))}</span></td>")
            html.append(f"<td>{chain_badge}</td>")
            html.append(f"<td><span class='badge'>{escape(str(top_src or '—'))}</span></td>")
            html.append(f"<td>{float(share or 0.0):.2f}</td>")
            html.append(f"<td>{base_score:.4f}</td>")
            html.append(f"<td>{push_val:.4f}</td>")
            html.append(f"<td>{int(doms or 0)}</td>")
            html.append(f"<td>{int(l3 or 0)}</td>")
            html.append(f"<td><button class='top3-btn' data-target='{top3_id}'>Top-3</button></td>")
            html.append("</tr>")

            edges = topk_edges.get(series, [])
            html.append(f"<tr class='top3-row' id='{top3_id}'><td colspan='11'>")
            mxs = float(event_strength_max.get(str(series), 0.0) or 0.0)
            b = event_boost(mxs)
            if edges:
                html.append("<div class='top3-box'>")
                html.append(
                    f"<div class='muted' style='margin:2px 0 8px'>"
                    f"event_boost = <b>x{b:.2f}</b> "
                    f"(max_strength={mxs:.1f} on latest events date)"
                    f"</div>"
                )
                html.append("<table class='top3-table'>")
                has_raw = any(e.get("push_raw") is not None for e in edges)
                if has_raw:
                    html.append("<thead><tr><th>src_series</th><th>share_sum</th><th>base_score</th><th>boosted_score</th><th>push_raw</th><th>edge_n</th><th>domains</th></tr></thead><tbody>")
                else:
                    html.append("<thead><tr><th>src_series</th><th>share_sum</th><th>base_score</th><th>boosted_score</th><th>edge_n</th><th>domains</th></tr></thead><tbody>")
                for e in edges:
                    boost_note = f"<div class='muted'>dst_boost_applied: x{b:.2f}</div>"
                    boosted_score = float(e.get("push_sum") or 0.0)
                    base_score = (boosted_score / b) if b > 0 else boosted_score
                    if has_raw:
                        html.append(
                            "<tr>"
                            f"<td>{escape(str(e.get('src_series') or '—'))}{boost_note}</td>"
                            f"<td>{float(e.get('share_sum') or 0.0):.4f}</td>"
                            f"<td>{base_score:.4f}</td>"
                            f"<td>{boosted_score:.4f}</td>"
                            f"<td>{float(e.get('push_raw') or 0.0):.4f}</td>"
                            f"<td>{int(e.get('edge_n') or 0)}</td>"
                            f"<td>{escape(preview_domains(e.get('domains_csv') or ''))}</td>"
                            "</tr>"
                        )
                    else:
                        html.append(
                            "<tr>"
                            f"<td>{escape(str(e.get('src_series') or '—'))}{boost_note}</td>"
                            f"<td>{float(e.get('share_sum') or 0.0):.4f}</td>"
                            f"<td>{base_score:.4f}</td>"
                            f"<td>{boosted_score:.4f}</td>"
                            f"<td>{int(e.get('edge_n') or 0)}</td>"
                            f"<td>{escape(preview_domains(e.get('domains_csv') or ''))}</td>"
                            "</tr>"
                        )
                html.append("</tbody></table></div>")
            else:
                html.append("<div class='top3-box'><span class='muted'>無 Top-3 edges</span></div>")
            html.append("</td></tr>")

        html.append("</tbody></table>")

        html.append("""
<div class=hint>
  <span class=pill>W_avg＝現在熱度；W_proj＝外來推力後的預測壓力（下一跳）</span>
  <span class=pill>Chain=YES＝這個系列的變紅主要是「被其他系列推動」</span>
  <span class=pill>右表的 Top src/share/push 用來指認「誰在推誰」</span>
</div>
""")

    else:
        html.append("<table><thead><tr>"
                    "<th>Series</th><th>domains</th><th>L3</th><th>W_avg</th>"
                    "</tr></thead><tbody>")
        for r in series_rows:
            series, doms, l3, wavg = r
            html.append("<tr>")
            html.append(f"<td><b>{escape(str(series))}</b></td>")
            html.append(f"<td>{int(doms or 0)}</td>")
            html.append(f"<td>{int(l3 or 0)}</td>")
            html.append(f"<td><b>{float(wavg or 0.0):.3f}</b></td>")
            html.append("</tr>")
        html.append("</tbody></table>")
        html.append("<div class=hint><span class=pill>目前尚未接入 chain / projected view（會自動降級顯示）。</span></div>")

    html.append("</div>")  # right card
    html.append("</div>")  # grid

    html.append("""
<script>
const rows = [...document.querySelectorAll("#domainTable tbody tr")];
const buttons = [...document.querySelectorAll(".controls button")];
const search = document.getElementById("search");

function setActive(btn){
  buttons.forEach(b=>b.classList.remove("active"));
  btn.classList.add("active");
}

function apply(){
  const mode = document.querySelector(".controls button.active").dataset.mode;
  const q = (search.value || "").toLowerCase();

  rows.forEach(r=>{
    let ok = true;
    const risk = r.dataset.risk;
    const level = r.dataset.level;
    const chain = r.dataset.chain;
    const text = (r.dataset.text || "").toLowerCase();

    if(mode==="event") ok = (risk==="事件");
    if(mode==="alert") ok = (risk==="事件" || risk==="警戒");
    if(mode==="sus")   ok = (risk==="事件" || risk==="警戒" || risk==="可疑");
    if(mode==="l3")    ok = (level==="L3");
    if(mode==="chain") ok = (chain==="1");

    if(q && !text.includes(q)) ok = false;
    r.style.display = ok ? "" : "none";
  });
}

buttons.forEach(b=>{
  b.addEventListener("click", ()=>{
    setActive(b);
    apply();
  });
});

search.addEventListener("input", apply);

document.querySelectorAll(".match").forEach(m=>{
  m.addEventListener("click", ()=>{
    const box = m.nextElementSibling;
    box.style.display = (box.style.display==="block") ? "none" : "block";
  });
});

const stormBtn = document.getElementById("stormToggle");
const seriesRows = [...document.querySelectorAll("tr.series-row")];

function applyStorm(on){
  seriesRows.forEach(r=>{
    const chain = (r.dataset.chain || "").toUpperCase();
    const push = parseFloat(r.dataset.push || "0");
    const ok = !on || (chain==="YES" && push>=0.08);
    r.style.display = ok ? "" : "none";
    const detail = r.nextElementSibling;
    if(detail && detail.classList.contains("top3-row")){
      if(!ok) detail.style.display = "none";
    }
  });
}

if(stormBtn){
  let stormOn = false;
  stormBtn.addEventListener("click", ()=>{
    stormOn = !stormOn;
    stormBtn.classList.toggle("active", stormOn);
    applyStorm(stormOn);
  });
}

document.querySelectorAll(".top3-btn").forEach(btn=>{
  btn.addEventListener("click", ()=>{
    const targetId = btn.dataset.target;
    const row = document.getElementById(targetId);
    if(!row) return;
    row.style.display = (row.style.display==="table-row") ? "none" : "table-row";
  });
});
</script>
""")

    html.append("</main></body></html>")

    with open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write("\n".join(html))

    print("Wrote", OUT_HTML, "(render_dashboard_v02.py upgraded + derived_events)")

if __name__ == "__main__":
    main()
