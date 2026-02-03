import json, sqlite3, time, statistics
from pathlib import Path
from datetime import datetime, timezone

DB = "radar.db"
OUT = "dashboard.html"
DOMAINS_JSON = "domains.json"

# --- helpers ---
def utc8(ts):
    return datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(
        timezone(datetime.now().astimezone().utcoffset())
    )

def median(xs):
    xs = [x for x in xs if x is not None]
    return statistics.median(xs) if xs else None

def load_domains():
    data = json.loads(Path(DOMAINS_JSON).read_text(encoding="utf-8"))
    rows = []
    for g in data.get("groups", []):
        series = g.get("id")
        for d, url in g.get("items", []):
            rows.append((d.strip().lower(), series, url))
    return rows

def ensure_domains(conn):
    conn.execute("CREATE TABLE IF NOT EXISTS domains (domain TEXT PRIMARY KEY, series TEXT, url TEXT)")
    for d, series, url in load_domains():
        conn.execute("INSERT OR REPLACE INTO domains(domain, series, url) VALUES(?,?,?)", (d, series, url))
    conn.commit()

def get_latest_ts(conn):
    row = conn.execute("SELECT MAX(ts) FROM metrics_30m").fetchone()
    return row[0] if row and row[0] else None

def get_latest_rows(conn, ts):
    q = """
    SELECT m.domain, d.series, d.url,
           m.requests_total, m.bandwidth_bytes, m.http_4xx, m.http_5xx,
           m.cf_mitigated, m.cf_challenged, m.bot_like_ratio,
           m.top_country_1, m.top_country_1_requests, m.top_country_2, m.top_country_2_requests,
           m.top_sig
    FROM metrics_30m m
    LEFT JOIN domains d ON d.domain = m.domain
    WHERE m.ts = ?
    """
    return conn.execute(q, (ts,)).fetchall()

def get_baseline_7d_same_slot(conn, domain, ts):
    # 同一時段：以 30 分鐘為 slot（0~47）
    slot = (ts // 1800) % 48
    # 取過去 7 天同 slot 的 requests_total
    start = ts - 7*24*3600
    q = """
    SELECT requests_total FROM metrics_30m
    WHERE domain = ? AND ts >= ? AND ts < ?
      AND ((ts/1800) % 48) = ?
    """
    rows = conn.execute(q, (domain, start, ts, slot)).fetchall()
    vals = [r[0] for r in rows if r and r[0] is not None]
    return median(vals)

def series_rollup(rows):
    # rows: latest rows
    out = {}
    for r in rows:
        domain, series = r[0], r[1] or "unknown"
        req = r[3] or 0
        out.setdefault(series, 0)
        out[series] += req
    return sorted(out.items(), key=lambda x: x[1], reverse=True)

def fmt_int(x):
    return f"{int(x):,}" if x is not None else "—"

def fmt_pct(x):
    return f"{x*100:.0f}%" if x is not None else "—"

def main():
    conn = sqlite3.connect(DB)
    ensure_domains(conn)

    latest_ts = get_latest_ts(conn)
    if not latest_ts:
        # 沒資料也要出一個空面板
        Path(OUT).write_text("<h1>Radar v0</h1><p>No data yet.</p>", encoding="utf-8")
        print("No data yet. Wrote empty dashboard.")
        return

    rows = get_latest_rows(conn, latest_ts)

    # 計算 anomaly（requests / 7d median same slot）
    enriched = []
    for r in rows:
        domain = r[0]
        req = r[3] or 0
        base = get_baseline_7d_same_slot(conn, domain, latest_ts)
        anomaly = (req / base) if (base and base > 0) else None
        enriched.append((r, base, anomaly))

    # 排序：先看 anomaly，再看 requests
    enriched.sort(key=lambda t: ((t[2] or 0), (t[0][3] or 0)), reverse=True)

    # series rollup
    roll = series_rollup(rows)

    ts_label = utc8(latest_ts).strftime("%Y-%m-%d %H:%M")

    # --- HTML ---
    html = []
    html.append(f"""<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Radar v0 — Distributed Domains</title>
<style>
body{{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;margin:0;padding:2rem;background:#fff;color:#111;line-height:1.5}}
h1{{margin:0 0 .5rem 0;font-size:1.6rem}}
.sub{{color:#666;margin-bottom:1.5rem}}
.grid{{display:grid;grid-template-columns:1fr;gap:1rem}}
@media(min-width:980px){{.grid{{grid-template-columns:1.1fr .9fr}}}}
.card{{border:1px solid rgba(0,0,0,.12);border-radius:14px;padding:1rem}}
table{{width:100%;border-collapse:collapse}}
th,td{{padding:.55rem .4rem;border-bottom:1px solid rgba(0,0,0,.08);vertical-align:top}}
th{{text-align:left;font-size:.9rem;color:#444}}
.badge{{display:inline-block;padding:.15rem .55rem;border-radius:999px;border:1px solid rgba(0,0,0,.15);font-size:.8rem;color:#444}}
.muted{{color:#777}}
a{{color:inherit;text-decoration:none;border-bottom:1px solid rgba(0,0,0,.15)}}
a:hover{{border-bottom-color:rgba(0,0,0,.35)}}
</style>
</head>
<body>
<h1>Radar v0</h1>
<div class="sub">Latest slot: <span class="badge">{ts_label}</span> · interval 30m · source: SQLite</div>
<div class="grid">
""")

    # Left: domain table
    html.append('<div class="card"><h2 style="margin:.2rem 0 1rem 0;font-size:1.1rem">Domains — anomaly first</h2>')
    html.append("<table><thead><tr>"
                "<th>Domain</th><th>Series</th><th>Req</th><th>Anom</th><th>CF Mitig</th><th>Top geo</th><th>Sig</th>"
                "</tr></thead><tbody>")

    for (r, base, anom) in enriched[:80]:
        domain, series, url = r[0], r[1] or "unknown", r[2] or f"https://{r[0]}/"
        req = r[3]
        mitig = r[7]
        c1, c1n, c2, c2n = r[10], r[11], r[12], r[13]
        sig = r[14] or "—"

        anom_txt = "—" if anom is None else f"{anom:.2f}×"
        geo_txt = "—"
        if c1:
            geo_txt = f"{c1} {fmt_int(c1n)}"
            if c2:
                geo_txt += f"<br><span class='muted'>{c2} {fmt_int(c2n)}</span>"

        html.append("<tr>"
                    f"<td><a href='{url}' target='_blank' rel='noopener noreferrer'>{domain}</a></td>"
                    f"<td class='muted'>{series}</td>"
                    f"<td>{fmt_int(req)}</td>"
                    f"<td>{anom_txt}</td>"
                    f"<td>{fmt_int(mitig)}</td>"
                    f"<td>{geo_txt}</td>"
                    f"<td class='muted'>{sig}</td>"
                    "</tr>")

    html.append("</tbody></table></div>")

    # Right: series rollup + quick notes
    html.append('<div class="card"><h2 style="margin:.2rem 0 1rem 0;font-size:1.1rem">Series heat (requests)</h2>')
    html.append("<table><thead><tr><th>Series</th><th>Req</th></tr></thead><tbody>")
    for s, v in roll:
        html.append(f"<tr><td class='muted'>{s}</td><td>{fmt_int(v)}</td></tr>")
    html.append("</tbody></table>")

    html.append("""
    <div style="margin-top:1.2rem" class="muted">
      <div><span class="badge">How to read</span></div>
      <p style="margin:.6rem 0 0 0">
        Anom = current 30m requests ÷ median of same timeslot over last 7 days.
        1.0× ≈ baseline, 2.0×+ ≈ meaningful deviation.
      </p>
      <p style="margin:.6rem 0 0 0">
        v0 stores only summaries (not raw logs). v1 can add: ASN, UA buckets, signature classifier, correlations.
      </p>
    </div>
    </div>
</div>
</body></html>
""")

    Path(OUT).write_text("".join(html), encoding="utf-8")
    print(f"Wrote {OUT} at slot {latest_ts}.")

if __name__ == "__main__":
    main()
