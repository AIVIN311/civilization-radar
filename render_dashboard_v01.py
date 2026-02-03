import json
import math
import sqlite3
from datetime import datetime

DB_PATH = "radar.db"
OUT_HTML = "dashboard_v01.html"

def heat(req: int) -> float:
    return math.log(1 + max(req, 0))

def toxin(mitigated: int, req: int, sig: str) -> float:
    # 最小版本：先用 mitigated/req 當毒性核心，再加上 sig 的加權
    if req <= 0:
        return 0.0
    base = mitigated / req
    bonus = 0.15 if sig in ("env_scan", "wp_scan", "config_scan") else 0.0
    return min(1.0, base + bonus)

def main():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # 取最新 slot
    cur.execute("SELECT MAX(slot) FROM snapshot")
    row = cur.fetchone()
    if not row or row[0] is None:
        raise RuntimeError("No snapshot data found. Run: python seed_from_snapshots.py")

    latest_slot = int(row[0])

    cur.execute("""
      SELECT ts, domain, series, req, mitigated, cf_served, origin_served, sig, top_countries_json
      FROM snapshot
      WHERE slot = ?
      ORDER BY req DESC
    """, (latest_slot,))
    rows = cur.fetchall()
    conn.close()

    # 系列熱度彙總
    series_sum = {}
    domain_cards = []
    latest_ts = rows[0][0] if rows else ""

    for ts, domain, series, req, mitigated, cf_served, origin_served, sig, top_json in rows:
        h = heat(req)
        tox = toxin(mitigated, req, sig)
        series_key = series or "unknown"
        series_sum[series_key] = series_sum.get(series_key, 0) + req

        top = {}
        try:
            top = json.loads(top_json or "{}")
        except:
            top = {}

        # 取 top 2 國家
        top2 = sorted(top.items(), key=lambda x: x[1], reverse=True)[:2]
        top2_text = "<br>".join([f"{k} {v}" for k, v in top2]) if top2 else "—"

        domain_cards.append({
            "domain": domain,
            "series": series_key,
            "req": req,
            "mitigated": mitigated,
            "heat": round(h, 3),
            "toxin": round(tox, 3),
            "sig": sig or "—",
            "top2": top2_text,
        })

    series_rank = sorted(series_sum.items(), key=lambda x: x[1], reverse=True)

    # 產生 HTML（極簡）
    def esc(s):
        return (s or "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

    lines = []
    lines.append("<!doctype html><html><head><meta charset='utf-8'>")
    lines.append("<meta name='viewport' content='width=device-width,initial-scale=1'>")
    lines.append("<title>雷達 v0.1</title>")
    lines.append("""
<style>
body{font-family:system-ui,-apple-system,Segoe UI,sans-serif;margin:0;background:#fff;color:#111}
main{max-width:1100px;margin:0 auto;padding:28px 18px}
h1{margin:0 0 10px;font-size:28px}
.meta{color:#666;margin-bottom:18px}
.grid{display:grid;grid-template-columns:1.3fr 1fr;gap:16px}
.card{border:1px solid #eee;border-radius:14px;padding:16px}
table{width:100%;border-collapse:collapse}
th,td{padding:10px 8px;border-bottom:1px solid #f1f1f1;vertical-align:top}
th{color:#666;font-weight:600;text-align:left}
small{color:#666}
.badge{display:inline-block;padding:2px 8px;border:1px solid #eee;border-radius:999px;font-size:12px;color:#444}
</style>
""")
    lines.append("</head><body><main>")
    lines.append("<h1>雷達 v0.1</h1>")
    lines.append(f"<div class='meta'>最新時段：{esc(latest_ts)} · slot={latest_slot} · 區間 30m · 來源：snapshots.jsonl</div>")
    lines.append("<div class='grid'>")

    # 左：域名表
    lines.append("<div class='card'><h3>領域 — 異常候選（以 req 排序）</h3>")
    lines.append("<table><thead><tr><th>領域</th><th>系列</th><th>req</th><th>Heat</th><th>Toxin</th><th>Top2</th><th>Sig</th></tr></thead><tbody>")
    for c in domain_cards:
        lines.append("<tr>")
        lines.append(f"<td><a href='https://{esc(c['domain'])}/' target='_blank' rel='noopener noreferrer'>{esc(c['domain'])}</a></td>")
        lines.append(f"<td>{esc(c['series'])}</td>")
        lines.append(f"<td>{c['req']}</td>")
        lines.append(f"<td>{c['heat']}</td>")
        lines.append(f"<td>{c['toxin']}</td>")
        lines.append(f"<td><small>{c['top2']}</small></td>")
        lines.append(f"<td><span class='badge'>{esc(c['sig'])}</span></td>")
        lines.append("</tr>")
    lines.append("</tbody></table></div>")

    # 右：系列熱度
    lines.append("<div class='card'><h3>系列熱度（總 req）</h3>")
    lines.append("<table><thead><tr><th>系列</th><th>req</th></tr></thead><tbody>")
    for s, v in series_rank:
        lines.append(f"<tr><td>{esc(s)}</td><td>{v}</td></tr>")
    lines.append("</tbody></table>")
    lines.append("<div style='margin-top:12px'><small>下一步：加入 Shift（7日中位數對比）→ 形成真正預警曲線。</small></div>")
    lines.append("</div>")

    lines.append("</div></main></body></html>")

    with open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"Wrote {OUT_HTML} (v0.1)")

if __name__ == "__main__":
    main()
