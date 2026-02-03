import json
import sqlite3
from datetime import datetime

DB_PATH = "radar.db"
OUT_HTML = "dashboard_v02.html"

def esc(s):
    return (str(s) if s is not None else "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

def f3(x):
    try:
        return f"{float(x):.3f}"
    except:
        return "—"

def main():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # 讀 v0.2：每個 domain 最新一筆（含 A / D / W）
    cur.execute("""
        SELECT ts, domain, series, req, sig, level_max, heat, A, D, Hstar, W, matched_json
        FROM v02_domain_latest
        ORDER BY W DESC
    """)
    rows = cur.fetchall()

    # 取最新 ts（用第一列）
    latest_ts = rows[0][0] if rows else ""

    # 讀 series：用最新 ts 對齊（同一時間切片）
    series_rows = []
    if latest_ts:
        cur.execute("""
            SELECT series, domains, heat_avg, A_avg, D_avg, Hstar_avg, W_avg, L3_domains
            FROM v02_series_latest
            WHERE ts = ?
            ORDER BY W_avg DESC
        """, (latest_ts,))
        series_rows = cur.fetchall()

    conn.close()

    # Domain cards
    domain_cards = []
    for ts, domain, series, req, sig, level_max, heat, A, D, Hstar, W, matched_json in rows:
        matched = []
        try:
            matched = json.loads(matched_json or "[]")
        except:
            matched = []

        domain_cards.append({
            "ts": ts,
            "domain": domain,
            "series": series or "unknown",
            "req": int(req or 0),
            "sig": sig or "—",
            "level": level_max or "—",
            "heat": f3(heat),
            "A": f3(A),
            "D": f3(D),
            "W": f3(W),
            "matched": ", ".join(matched[:4]) if matched else "—",
        })

    # Series cards
    series_cards = []
    for series, domains, heat_avg, A_avg, D_avg, Hstar_avg, W_avg, L3_domains in series_rows:
        series_cards.append({
            "series": series or "unknown",
            "domains": int(domains or 0),
            "L3": int(L3_domains or 0),
            "heat_avg": f3(heat_avg),
            "A_avg": f3(A_avg),
            "D_avg": f3(D_avg),
            "W_avg": f3(W_avg),
        })

    # HTML
    lines = []
    lines.append("<!doctype html><html><head><meta charset='utf-8'>")
    lines.append("<meta name='viewport' content='width=device-width,initial-scale=1'>")
    lines.append("<title>文明雷達 v0.2</title>")
    lines.append("""
<style>
body{font-family:system-ui,-apple-system,Segoe UI,sans-serif;margin:0;background:#fff;color:#111}
main{max-width:1200px;margin:0 auto;padding:28px 18px}
h1{margin:0 0 10px;font-size:28px}
.meta{color:#666;margin-bottom:18px;line-height:1.5}
.grid{display:grid;grid-template-columns:1.6fr 1fr;gap:16px}
.card{border:1px solid #eee;border-radius:14px;padding:16px}
table{width:100%;border-collapse:collapse}
th,td{padding:10px 8px;border-bottom:1px solid #f1f1f1;vertical-align:top}
th{color:#666;font-weight:600;text-align:left}
small{color:#666}
.badge{display:inline-block;padding:2px 8px;border:1px solid #eee;border-radius:999px;font-size:12px;color:#444}
.k{font-variant-numeric:tabular-nums}
.w{font-weight:700}
.l3{font-weight:700}
.dim{color:#777}
</style>
""")
    lines.append("</head><body><main>")
    lines.append("<h1>文明雷達 v0.2</h1>")
    lines.append(f"<div class='meta'>最新時段：{esc(latest_ts)} · 區間 30m · 資料來源：metrics_v02 → v02_domain_latest / v02_series_latest<br><span class='dim'>排序依據：W（預警指數） · 指標：Level（探測深度）/ Heat（當下結構熱度）/ A（異常偏離）/ D（同步擴散）/ W（時間累積預警）</span></div>")
    lines.append("<div class='grid'>")

    # Left: domain table
    lines.append("<div class='card'><h3>領域預警榜（以 W 排序）</h3>")
    lines.append("<table><thead><tr>")
    lines.append("<th>Domain</th><th>Series</th><th class='k'>req</th><th>Level</th><th class='k'>Heat</th><th class='k'>A</th><th class='k'>D</th><th class='k'>W</th><th>Matched</th><th>Sig</th>")
    lines.append("</tr></thead><tbody>")

    for c in domain_cards:
        level_cls = "l3" if c["level"] == "L3" else ""
        lines.append("<tr>")
        lines.append(f"<td><a href='https://{esc(c['domain'])}/' target='_blank' rel='noopener noreferrer'>{esc(c['domain'])}</a></td>")
        lines.append(f"<td>{esc(c['series'])}</td>")
        lines.append(f"<td class='k'>{c['req']}</td>")
        lines.append(f"<td class='{level_cls}'>{esc(c['level'])}</td>")
        lines.append(f"<td class='k'>{c['heat']}</td>")
        lines.append(f"<td class='k'>{c['A']}</td>")
        lines.append(f"<td class='k'>{c['D']}</td>")
        lines.append(f"<td class='k w'>{c['W']}</td>")
        lines.append(f"<td><small>{esc(c['matched'])}</small></td>")
        lines.append(f"<td><span class='badge'>{esc(c['sig'])}</span></td>")
        lines.append("</tr>")

    lines.append("</tbody></table></div>")

    # Right: series table
    lines.append("<div class='card'><h3>系列預警榜（同一時段，W_avg 排序）</h3>")
    if not series_cards:
        lines.append("<div><small>（無 series 彙總資料：請確認 v02_series_latest view 存在且 upgrade_to_v02.py 已成功建立。）</small></div>")
    else:
        lines.append("<table><thead><tr>")
        lines.append("<th>Series</th><th class='k'>domains</th><th class='k'>L3</th><th class='k'>Heat_avg</th><th class='k'>A_avg</th><th class='k'>D_avg</th><th class='k'>W_avg</th>")
        lines.append("</tr></thead><tbody>")
        for s in series_cards:
            lines.append("<tr>")
            lines.append(f"<td>{esc(s['series'])}</td>")
            lines.append(f"<td class='k'>{s['domains']}</td>")
            lines.append(f"<td class='k l3'>{s['L3']}</td>")
            lines.append(f"<td class='k'>{s['heat_avg']}</td>")
            lines.append(f"<td class='k'>{s['A_avg']}</td>")
            lines.append(f"<td class='k'>{s['D_avg']}</td>")
            lines.append(f"<td class='k w'>{s['W_avg']}</td>")
            lines.append("</tr>")
        lines.append("</tbody></table>")

    lines.append("<div style='margin-top:12px'><small>解讀：A↑＝相對自身基線升溫，D↑＝同時段 L2/L3 擴散比例上升，W↑＝時間累積後的預警指數。L3 高且 W 高，通常代表「深層探測」同步化。</small></div>")
    lines.append("</div>")  # right card

    lines.append("</div></main></body></html>")

    with open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"Wrote {OUT_HTML} (v0.2)")

if __name__ == "__main__":
    main()
