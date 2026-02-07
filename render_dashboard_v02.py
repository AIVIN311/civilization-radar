import argparse
import json
import sqlite3
from html import escape

from src.settings import add_common_args, from_args
from src.version import __version__


def table_exists(cur, name: str) -> bool:
    row = cur.execute(
        "SELECT 1 FROM sqlite_master WHERE (type='table' OR type='view') AND name=? LIMIT 1",
        (name,),
    ).fetchone()
    return bool(row)


def fetch_domain_rows(cur):
    if not table_exists(cur, "v02_domain_latest"):
        return []
    events = {}
    if table_exists(cur, "events_v01"):
        for r in cur.execute(
            """
            WITH ranked AS (
              SELECT domain,event_type,strength,req_key,event_level,matched_signals_json,
                     ROW_NUMBER() OVER (PARTITION BY domain ORDER BY date DESC,id DESC) AS rn
              FROM events_v01
            )
            SELECT domain,event_type,strength,req_key,event_level,matched_signals_json
            FROM ranked WHERE rn=1
            """
        ).fetchall():
            events[str(r[0]).lower()] = r[1:]
    rows = cur.execute(
        """
        SELECT domain,series,level_max,A,W,sig,matched_json
        FROM v02_domain_latest
        ORDER BY W DESC, A DESC
        """
    ).fetchall()
    out = []
    for domain, series, level_max, A, W, sig, matched_json in rows:
        ev = events.get(str(domain).lower())
        out.append(
            {
                "domain": str(domain),
                "series": str(series),
                "level": str(level_max or "L1"),
                "A": float(A or 0.0),
                "W": float(W or 0.0),
                "sig": str(sig or ""),
                "matched": str(matched_json or "[]"),
                "event_type": str(ev[0]) if ev else "",
                "event_strength": float(ev[1] or 0.0) if ev else 0.0,
                "event_req_key": str(ev[2] or "") if ev else "",
                "event_level": str(ev[3] or "L1") if ev else "L1",
                "event_matched": str(ev[4] or "[]") if ev else "[]",
            }
        )
    return out


def fetch_event_rows(cur):
    if not table_exists(cur, "events_v01"):
        return []
    return [
        {
            "date": str(r[0]),
            "domain": str(r[1]),
            "series": str(r[2]),
            "event_type": str(r[3]),
            "event_level": str(r[4] or "L1"),
            "strength": float(r[5] or 0.0),
            "ratio": float(r[6] or 0.0),
            "matched": str(r[7] or "[]"),
        }
        for r in cur.execute(
            """
            SELECT date,domain,series,event_type,event_level,strength,ratio,matched_signals_json
            FROM events_v01
            ORDER BY date DESC, strength DESC, id DESC
            LIMIT 200
            """
        ).fetchall()
    ]


def fetch_chain_rows(cur):
    if not table_exists(cur, "v03_series_chain_latest"):
        return [], {}
    try:
        rows = cur.execute(
            """
            SELECT series,W_avg,W_proj,status,chain_flag,top_src,share,push,push_raw,base_push,boosted_push,delta_boost,
                   geo_profile,geo_factor,tw_rank_score,domains,L3_domains,max_event_level
            FROM v03_series_chain_latest
            ORDER BY W_proj DESC, W_avg DESC
            """
        ).fetchall()
        has_geo = True
    except sqlite3.OperationalError:
        rows = cur.execute(
            """
            SELECT series,W_avg,W_proj,status,chain_flag,top_src,share,push,push_raw,base_push,boosted_push,delta_boost,domains,L3_domains,max_event_level
            FROM v03_series_chain_latest
            ORDER BY W_proj DESC, W_avg DESC
            """
        ).fetchall()
        has_geo = False
    series_rows = [
        {
            "series": str(r[0]),
            "W_avg": float(r[1] or 0.0),
            "W_proj": float(r[2] or 0.0),
            "status": str(r[3] or ""),
            "chain_flag": int(r[4] or 0),
            "top_src": str(r[5] or ""),
            "share": float(r[6] or 0.0),
            "push": float(r[7] or 0.0),
            "push_raw": float(r[8] or 0.0),
            "base_push": float(r[9] or 0.0),
            "boosted_push": float(r[10] or 0.0),
            "delta_boost": float(r[11] or 0.0),
            "geo_profile": str(r[12] or "") if has_geo else "",
            "geo_factor": float(r[13] or 0.0) if has_geo else 0.0,
            "tw_rank_score": float(r[14] or 0.0) if has_geo else float(r[10] or 0.0),
            "domains": int(r[15] or 0) if has_geo else int(r[12] or 0),
            "L3_domains": int(r[16] or 0) if has_geo else int(r[13] or 0),
            "max_event_level": str(r[17] or "L1") if has_geo else str(r[14] or "L1"),
        }
        for r in rows
    ]
    edges = {}
    if table_exists(cur, "v03_chain_edges_latest"):
        top_rows = cur.execute(
            """
            WITH ranked AS (
              SELECT dst_series,src_series,share,base_score,boosted_score,delta_boost,boost_multiplier,edge_n,
                     src_event_type,src_event_strength,src_event_decayed_strength,max_event_level,src_matched_signals_json,
                     ROW_NUMBER() OVER (PARTITION BY dst_series ORDER BY boosted_score DESC) AS rn
              FROM v03_chain_edges_latest
            )
            SELECT dst_series,src_series,share,base_score,boosted_score,delta_boost,boost_multiplier,edge_n,
                   src_event_type,src_event_strength,src_event_decayed_strength,max_event_level,src_matched_signals_json
            FROM ranked
            WHERE rn<=3
            ORDER BY dst_series,rn
            """
        ).fetchall()
        for r in top_rows:
            dst = str(r[0])
            edges.setdefault(dst, []).append(
                {
                    "src_series": str(r[1]),
                    "share": float(r[2] or 0.0),
                    "base_score": float(r[3] or 0.0),
                    "boosted_score": float(r[4] or 0.0),
                    "delta_boost": float(r[5] or 0.0),
                    "event_boost": float(r[6] or 1.0),
                    "edge_n": int(r[7] or 0),
                    "event_type": str(r[8] or ""),
                    "strength": float(r[9] or 0.0),
                    "decayed_strength": float(r[10] or 0.0),
                    "event_level": str(r[11] or "L1"),
                    "matched_signals_json": str(r[12] or "[]"),
                }
            )
    return series_rows, edges


def render(cfg, latest_ts, domains, events, chains, top3):
    html = []
    html.append("<!doctype html><html><head><meta charset='utf-8'>")
    html.append("<meta name='viewport' content='width=device-width, initial-scale=1'>")
    html.append("<title>Civilization Radar v0.4</title>")
    html.append(
        """
<style>
body{font-family:Segoe UI,system-ui,sans-serif;background:#fbfcfd;color:#111;margin:0}
main{max-width:1400px;margin:auto;padding:20px}
h1{margin:0 0 6px}
.meta{color:#666;font-size:13px;margin-bottom:14px}
.controls{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:14px}
button{padding:6px 10px;border:1px solid #ccc;background:#fff;border-radius:8px;cursor:pointer}
button.active{background:#111;color:#fff;border-color:#111}
.grid{display:grid;grid-template-columns:1fr;gap:14px}
.card{background:#fff;border:1px solid #e8eaee;border-radius:12px;padding:12px}
table{width:100%;border-collapse:collapse}
th,td{font-size:13px;text-align:left;border-bottom:1px solid #f1f3f6;padding:8px}
th{color:#555}
.lv.L3{color:#b91c1c;font-weight:700}
.lv.L2{color:#c2410c;font-weight:700}
.lv.L1{color:#555;font-weight:700}
.muted{color:#888}
.top3{display:none;background:#fafafa}
.badge{display:inline-block;padding:2px 7px;border:1px solid #ddd;border-radius:999px;font-size:11px}
</style>
"""
    )
    html.append("</head><body><main>")
    html.append("<h1>Civilization Radar v0.4</h1>")
    html.append(
        f"<div class='meta'>version={escape(__version__)} | latest_ts={escape(str(latest_ts))} | "
        f"half_life_days={cfg['half_life_days']} | output={escape(cfg['output_dir'])}</div>"
    )
    html.append(
        """
<div class="controls">
  <button class="active" data-mode="all">全部</button>
  <button data-mode="l3">只看 L3</button>
</div>
"""
    )

    html.append("<div class='grid'>")

    html.append("<div class='card'><h3>Domain 榜</h3><table id='domainTable'><thead><tr>")
    html.append("<th>domain</th><th>series</th><th>level</th><th>A</th><th>W</th><th>event</th><th>matched</th>")
    html.append("</tr></thead><tbody>")
    for d in domains:
        level = escape(d["level"])
        ev_text = "—"
        if d["event_type"]:
            ev_text = f"{escape(d['event_type'])} | s={d['event_strength']:.2f} | {escape(d['event_req_key'])}"
        html.append(
            f"<tr data-level='{escape(d['level'])}'>"
            f"<td>{escape(d['domain'])}</td>"
            f"<td>{escape(d['series'])}</td>"
            f"<td><span class='lv {level}'>{level}</span></td>"
            f"<td>{d['A']:.3f}</td>"
            f"<td>{d['W']:.3f}</td>"
            f"<td><span class='badge'>{ev_text}</span></td>"
            f"<td>{escape(d['matched'])}</td>"
            "</tr>"
        )
    html.append("</tbody></table></div>")

    html.append("<div class='card'><h3>事件列表</h3><table id='eventTable'><thead><tr>")
    html.append("<th>date</th><th>domain</th><th>series</th><th>type</th><th>level</th><th>strength</th><th>ratio</th><th>matched</th>")
    html.append("</tr></thead><tbody>")
    for e in events:
        lvl = escape(e["event_level"])
        html.append(
            f"<tr data-level='{lvl}'>"
            f"<td>{escape(e['date'])}</td>"
            f"<td>{escape(e['domain'])}</td>"
            f"<td>{escape(e['series'])}</td>"
            f"<td>{escape(e['event_type'])}</td>"
            f"<td><span class='lv {lvl}'>{lvl}</span></td>"
            f"<td>{e['strength']:.2f}</td>"
            f"<td>{e['ratio']:.3f}</td>"
            f"<td>{escape(e['matched'])}</td>"
            "</tr>"
        )
    html.append("</tbody></table></div>")

    html.append("<div class='card'><h3>鏈式列表</h3><table id='chainTable'><thead><tr>")
    html.append(
        "<th>series</th><th>W_avg</th><th>W_proj</th><th>base</th><th>boosted</th><th>delta</th>"
        "<th>geo_factor</th><th>tw_rank</th><th>top_src</th><th>L3</th><th>Top-3</th>"
    )
    html.append("</tr></thead><tbody>")
    for c in chains:
        sid = escape(c["series"])
        row_id = f"top3_{sid.replace('.', '_').replace('-', '_')}"
        lvl = escape(c["max_event_level"])
        html.append(
            f"<tr data-level='{lvl}'>"
            f"<td>{sid}</td>"
            f"<td>{c['W_avg']:.3f}</td>"
            f"<td>{c['W_proj']:.3f}</td>"
            f"<td>{c['base_push']:.4f}</td>"
            f"<td>{c['boosted_push']:.4f}</td>"
            f"<td>{c['delta_boost']:.4f}</td>"
            f"<td>{c['geo_factor']:.4f}</td>"
            f"<td>{c['tw_rank_score']:.4f}</td>"
            f"<td>{escape(c['top_src'])}</td>"
            f"<td>{c['L3_domains']}</td>"
            f"<td><button class='toggle' data-target='{row_id}'>Top-3</button></td>"
            "</tr>"
        )
        html.append(f"<tr class='top3' id='{row_id}' data-level='{lvl}'><td colspan='11'>")
        rows = top3.get(c["series"], [])
        if not rows:
            html.append("<span class='muted'>無 Top-3 edges</span>")
        else:
            html.append("<table><thead><tr>")
            html.append("<th>src</th><th>share</th><th>base</th><th>boosted</th><th>delta</th><th>event_boost</th><th>strength</th><th>decayed</th><th>event</th><th>matched</th>")
            html.append("</tr></thead><tbody>")
            for r in rows:
                html.append(
                    "<tr>"
                    f"<td>{escape(r['src_series'])}</td>"
                    f"<td>{r['share']:.4f}</td>"
                    f"<td>{r['base_score']:.4f}</td>"
                    f"<td>{r['boosted_score']:.4f}</td>"
                    f"<td>{r['delta_boost']:.4f}</td>"
                    f"<td>x{r['event_boost']:.2f}</td>"
                    f"<td>{r['strength']:.2f}</td>"
                    f"<td>{r['decayed_strength']:.2f}</td>"
                    f"<td>{escape(r['event_type'])}</td>"
                    f"<td>{escape(r['matched_signals_json'])}</td>"
                    "</tr>"
                )
            html.append("</tbody></table>")
        html.append("</td></tr>")
    html.append("</tbody></table></div>")

    html.append("</div>")
    html.append(
        """
<script>
const btns = [...document.querySelectorAll('.controls button')];
const tables = ['domainTable','eventTable','chainTable'];
function apply(mode){
  tables.forEach(id=>{
    document.querySelectorAll(`#${id} tbody tr`).forEach(tr=>{
      if(tr.classList.contains('top3')) return;
      const lvl = (tr.dataset.level || 'L1').toUpperCase();
      tr.style.display = (mode==='l3' && lvl!=='L3') ? 'none' : '';
      const next = tr.nextElementSibling;
      if(next && next.classList.contains('top3') && tr.style.display==='none'){
        next.style.display='none';
      }
    });
  });
}
btns.forEach(b=>b.addEventListener('click',()=>{
  btns.forEach(x=>x.classList.remove('active'));
  b.classList.add('active');
  apply(b.dataset.mode);
}));
document.querySelectorAll('.toggle').forEach(b=>b.addEventListener('click',()=>{
  const row = document.getElementById(b.dataset.target);
  if(!row) return;
  row.style.display = (row.style.display==='table-row') ? 'none' : 'table-row';
}));
</script>
"""
    )
    html.append("</main></body></html>")
    return "\n".join(html)


def main():
    parser = argparse.ArgumentParser()
    add_common_args(parser, include_half_life=True)
    args = parser.parse_args()
    cfg = from_args(args)

    con = sqlite3.connect(cfg["db_path"])
    cur = con.cursor()
    latest_ts = cur.execute("SELECT MAX(ts) FROM metrics_v02").fetchone()[0]
    if not latest_ts:
        raise SystemExit("metrics_v02 is empty. Run upgrade_to_v02.py")

    domains = fetch_domain_rows(cur)
    events = fetch_event_rows(cur)
    chains, top3 = fetch_chain_rows(cur)
    con.close()

    html = render(cfg, latest_ts, domains, events, chains, top3)
    with open(cfg["out_html"], "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Wrote {cfg['out_html']}")


if __name__ == "__main__":
    main()
