import sqlite3
import math
from html import escape

DB_PATH = "radar.db"
OUT_HTML = "dashboard_v02.html"

# ======= v0.21 risk thresholds (index-like, after log1p) =======
# 你可以之後微調這四條線
TH_BG = 1.20     # 綠/黃
TH_SUS = 1.80    # 黃/橘
TH_ALR = 2.30    # 橘/紅

SPARK_K = 16     # sparkline 回看點數（跟 upgrade_to_v02.py 的 K 對齊最好）


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def risk_bucket(W: float, level_max: str):
    """
    回傳：燈號顏色 class、文字 label
    讓 L3 有一點額外偏置：同樣 W 下，L3 更像警報系統。
    """
    w = float(W or 0.0)
    if level_max == "L3":
        w += 0.08  # 小小偏置：不要太大，避免扭曲排序

    if w >= TH_ALR:
        return "r-red", "事件"
    if w >= TH_SUS:
        return "r-orange", "警戒"
    if w >= TH_BG:
        return "r-yellow", "可疑"
    return "r-green", "背景"


def arrow(delta: float):
    if delta > 0.10:
        return "↑", "up"
    if delta < -0.10:
        return "↓", "down"
    return "→", "flat"


def svg_spark(values, width=140, height=22, pad=2):
    """
    產生一條超輕量 sparkline（SVG polyline），不用 matplotlib。
    values: list[float]
    """
    if not values:
        return "<span class='muted'>—</span>"

    vs = [float(v) for v in values]
    vmin = min(vs)
    vmax = max(vs)
    if abs(vmax - vmin) < 1e-9:
        vmax = vmin + 1e-9

    n = len(vs)
    xs = []
    ys = []
    for i, v in enumerate(vs):
        x = pad + (width - 2 * pad) * (i / max(1, n - 1))
        # 上方為小值，下方為大值（反轉）
        y = pad + (height - 2 * pad) * (1.0 - (v - vmin) / (vmax - vmin))
        xs.append(x)
        ys.append(y)

    pts = " ".join([f"{xs[i]:.1f},{ys[i]:.1f}" for i in range(n)])
    last = vs[-1]
    return f"""
    <svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" aria-label="W sparkline">
      <polyline points="{pts}" fill="none" stroke="currentColor" stroke-width="1.6" />
      <circle cx="{xs[-1]:.1f}" cy="{ys[-1]:.1f}" r="1.8" fill="currentColor"></circle>
      <title>W last={last:.3f}</title>
    </svg>
    """


def fetch_latest_ts(cur):
    row = cur.execute("SELECT MAX(ts) FROM metrics_v02").fetchone()
    if not row or not row[0]:
        raise RuntimeError("No metrics_v02 found. Run: python upgrade_to_v02.py")
    return row[0]


def fetch_prev_ts(cur, latest_ts):
    row = cur.execute(
        "SELECT MAX(ts) FROM metrics_v02 WHERE ts < ?",
        (latest_ts,)
    ).fetchone()
    return row[0] if row and row[0] else None


def fetch_domain_latest(cur):
    return cur.execute("""
      SELECT domain, series, req, level_max, heat, A, D, W, matched_json, sig
      FROM v02_domain_latest
      ORDER BY W DESC, heat DESC
    """).fetchall()


def fetch_series_latest(cur, latest_ts):
    return cur.execute("""
      SELECT series, domains, L3_domains, heat_avg, A_avg, D_avg, W_avg
      FROM v02_series_latest
      WHERE ts = ?
      ORDER BY W_avg DESC
    """, (latest_ts,)).fetchall()


def fetch_domain_prevW_map(cur, prev_ts):
    if not prev_ts:
        return {}
    rows = cur.execute("""
      SELECT domain, W
      FROM metrics_v02
      WHERE ts = ?
    """, (prev_ts,)).fetchall()
    return {r[0]: float(r[1] or 0.0) for r in rows}


def fetch_domain_sparks(cur, latest_ts, k=SPARK_K):
    """
    抓每個 domain 最近 k 筆 W，回傳 dict[domain] -> list[W]
    做法：先找出 latest_ts 之前（含 latest_ts）的最近 k 個 ts，然後一次查。
    """
    # 先取最近 k 個 ts（全域）
    ts_rows = cur.execute("""
      SELECT DISTINCT ts
      FROM metrics_v02
      WHERE ts <= ?
      ORDER BY ts DESC
      LIMIT ?
    """, (latest_ts, k)).fetchall()
    ts_list = [r[0] for r in ts_rows][::-1]  # 由舊到新

    if not ts_list:
        return {}, []

    # 取所有 domain 在這些 ts 的 W
    placeholders = ",".join(["?"] * len(ts_list))
    rows = cur.execute(f"""
      SELECT ts, domain, W
      FROM metrics_v02
      WHERE ts IN ({placeholders})
      ORDER BY ts ASC
    """, ts_list).fetchall()

    by_domain = {}
    for ts, domain, W in rows:
        by_domain.setdefault(domain, {})[ts] = float(W or 0.0)

    sparks = {}
    for domain, m in by_domain.items():
        sparks[domain] = [m.get(ts, 0.0) for ts in ts_list]

    return sparks, ts_list


def main():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    latest_ts = fetch_latest_ts(cur)
    prev_ts = fetch_prev_ts(cur, latest_ts)

    domains = fetch_domain_latest(cur)
    series_rows = fetch_series_latest(cur, latest_ts)

    prevW_map = fetch_domain_prevW_map(cur, prev_ts)
    sparks, ts_list = fetch_domain_sparks(cur, latest_ts, SPARK_K)

    con.close()

    # ---------- HTML ----------
    lines = []
    lines.append("<!doctype html><html><head><meta charset='utf-8'>")
    lines.append("<meta name='viewport' content='width=device-width,initial-scale=1'>")
    lines.append("<title>文明雷達 v0.2（戰情中心）</title>")
    lines.append("""
<style>
body{font-family:system-ui,-apple-system,Segoe UI,sans-serif;margin:0;background:#fff;color:#111}
main{max-width:1220px;margin:0 auto;padding:28px 18px}
h1{margin:0 0 10px;font-size:28px}
.meta{color:#666;margin-bottom:18px;line-height:1.5}
.grid{display:grid;grid-template-columns:1.6fr 1fr;gap:16px;align-items:start}
.card{border:1px solid #eee;border-radius:14px;padding:16px}
table{width:100%;border-collapse:collapse}
th,td{padding:10px 8px;border-bottom:1px solid #f1f1f1;vertical-align:top}
th{color:#666;font-weight:650;text-align:left;font-size:13px}
td{font-size:14px}
small{color:#666}
.badge{display:inline-block;padding:2px 8px;border:1px solid #eee;border-radius:999px;font-size:12px;color:#444}
.muted{color:#888}
.kpi{display:flex;gap:10px;flex-wrap:wrap;margin-top:10px}
.kpi .pill{border:1px solid #eee;border-radius:999px;padding:6px 10px;font-size:12px;color:#444}
.spark{color:#111} /* SVG uses currentColor */
.delta{font-size:12px;padding:2px 6px;border-radius:8px;border:1px solid #eee;display:inline-block}
.delta.up{color:#0b6}
.delta.down{color:#c33}
.delta.flat{color:#888}

/* 戰情燈號 */
.r{display:inline-flex;align-items:center;gap:8px}
.dot{width:10px;height:10px;border-radius:999px;display:inline-block}
.r-green .dot{background:#18a058}
.r-yellow .dot{background:#f0b429}
.r-orange .dot{background:#f97316}
.r-red .dot{background:#ef4444}
.r .label{font-size:12px;color:#444;border:1px solid #eee;border-radius:999px;padding:2px 8px}

/* Level */
.lv{font-weight:700}
.lv.L3{color:#b91c1c}
.lv.L2{color:#c2410c}
.lv.L1{color:#444}
</style>
""")
    lines.append("</head><body><main>")
    lines.append("<h1>文明雷達 v0.2（戰情中心）</h1>")

    # meta + thresholds
    lines.append(f"<div class='meta'>最新時段：{escape(latest_ts)} · 區間 30m · 資料來源：metrics_v02 → v02_domain_latest / v02_series_latest<br>"
                 f"排序依據：W（預警指數） · 指標：Level / Heat / A / D / W · sparkline：最近 {SPARK_K} 個時段<br>"
                 f"門檻：背景&lt;{TH_BG:.2f}，可疑≥{TH_BG:.2f}，警戒≥{TH_SUS:.2f}，事件≥{TH_ALR:.2f}（L3 會有輕微偏置）</div>")

    lines.append("<div class='grid'>")

    # -------- left: domain table --------
    lines.append("<div class='card'>")
    lines.append("<h3>領域預警榜（以 W 排序）</h3>")
    lines.append("<table><thead><tr>"
                 "<th>燈號</th><th>Domain</th><th>Series</th><th>req</th><th>Level</th>"
                 "<th>W</th><th>Δ</th><th>Heat</th><th>A</th><th>D</th><th>W 曲線</th><th>Matched</th><th>Sig</th>"
                 "</tr></thead><tbody>")

    for r in domains:
        domain, series, req, level_max, heat, A, D, W, matched_json, sig = r
        domain_s = escape(domain)
        series_s = escape(series or "unknown")
        sig_s = escape(sig or "—")
        matched_s = escape(matched_json or "—")

        Wv = float(W or 0.0)
        prevW = float(prevW_map.get(domain, Wv))
        dW = Wv - prevW
        arr, cls = arrow(dW)

        rb_class, rb_label = risk_bucket(Wv, level_max or "L1")

        spark_vals = sparks.get(domain, [])
        spark_html = svg_spark(spark_vals)

        lines.append("<tr>")
        lines.append(f"<td><span class='r {rb_class}'><span class='dot'></span><span class='label'>{rb_label}</span></span></td>")
        lines.append(f"<td><a href='https://{domain_s}/' target='_blank' rel='noopener noreferrer'>{domain_s}</a></td>")
        lines.append(f"<td>{series_s}</td>")
        lines.append(f"<td>{int(req or 0)}</td>")
        lv = (level_max or "L1").upper()
        lines.append(f"<td><span class='lv {lv}'>{lv}</span></td>")
        lines.append(f"<td><b>{Wv:.3f}</b></td>")
        lines.append(f"<td><span class='delta {cls}'>{arr} {dW:+.3f}</span></td>")
        lines.append(f"<td>{float(heat or 0.0):.3f}</td>")
        lines.append(f"<td>{float(A or 0.0):.3f}</td>")
        lines.append(f"<td>{float(D or 0.0):.3f}</td>")
        lines.append(f"<td class='spark'>{spark_html}</td>")
        lines.append(f"<td><small>{matched_s}</small></td>")
        lines.append(f"<td><span class='badge'>{sig_s}</span></td>")
        lines.append("</tr>")

    lines.append("</tbody></table>")
    lines.append("</div>")

    # -------- right: series table --------
    lines.append("<div class='card'>")
    lines.append("<h3>系列預警榜（W_avg 排序）</h3>")
    lines.append("<table><thead><tr>"
                 "<th>Series</th><th>domains</th><th>L3</th><th>Heat_avg</th><th>A_avg</th><th>D_avg</th><th>W_avg</th>"
                 "</tr></thead><tbody>")
    for s in series_rows:
        series, domains_n, l3_n, heat_avg, A_avg, D_avg, W_avg = s
        lines.append("<tr>")
        lines.append(f"<td>{escape(series)}</td>")
        lines.append(f"<td>{int(domains_n or 0)}</td>")
        lines.append(f"<td>{int(l3_n or 0)}</td>")
        lines.append(f"<td>{float(heat_avg or 0.0):.3f}</td>")
        lines.append(f"<td>{float(A_avg or 0.0):.3f}</td>")
        lines.append(f"<td>{float(D_avg or 0.0):.3f}</td>")
        lines.append(f"<td><b>{float(W_avg or 0.0):.3f}</b></td>")
        lines.append("</tr>")
    lines.append("</tbody></table>")

    lines.append("<div class='kpi'>"
                 "<span class='pill'>解讀：W↑＝時間累積預警；Δ↑＝短期升溫；Level=L3 且燈號偏紅 → 優先級最高</span>"
                 "<span class='pill'>下一刀（你一說我就做）：展開 matched（點擊展開）、只顯示 L3 的警報模式</span>"
                 "</div>")

    lines.append("</div>")  # right card

    lines.append("</div>")  # grid
    lines.append("</main></body></html>")

    with open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"Wrote {OUT_HTML} (v0.2 war-room)")


if __name__ == "__main__":
    main()
