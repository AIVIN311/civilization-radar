import argparse
import json
import sqlite3
from html import escape
from pathlib import Path

from src.persistence_v1 import (
    build_delta_series_from_db,
    compute_event_kernel,
    compute_tag_persistence,
    load_persistence_config,
)
from src.settings import add_common_args, from_args
from src.version import __version__


def table_exists(cur, name: str) -> bool:
    row = cur.execute(
        "SELECT 1 FROM sqlite_master WHERE (type='table' OR type='view') AND name=? LIMIT 1",
        (name,),
    ).fetchone()
    return bool(row)


def parse_explain_payload(raw_value):
    raw = str(raw_value or "").strip()
    if not raw:
        return {}, "{}", True
    try:
        payload = json.loads(raw)
    except Exception:
        fallback = f"Invalid explain JSON\n{raw}"
        return {"error": "Invalid explain JSON", "raw": raw}, fallback, False
    pretty = json.dumps(payload, ensure_ascii=False, indent=2)
    return payload, pretty, True


def _safe_profile_token(value: str) -> str:
    raw = str(value or "").strip().lower()
    if not raw:
        return "unknown"
    out = []
    for ch in raw:
        if ch.isalnum() or ch in ("_", "-"):
            out.append(ch)
        else:
            out.append("_")
    token = "".join(out).strip("_")
    return token or "unknown"


def write_persistence_outputs(cfg, latest_ts, geo_profile, persistence_state, kernel_state):
    derived_dir = Path(cfg["output_dir"]) / "derived"
    derived_dir.mkdir(parents=True, exist_ok=True)
    token = _safe_profile_token(geo_profile)

    persistence_payload = {
        "ts": str(persistence_state.get("latest_ts") or latest_ts or ""),
        "geo": str(geo_profile or ""),
        "persistence_v1": {
            "window": int(persistence_state.get("window") or 0),
            "tags": list(persistence_state.get("tags") or []),
        },
    }
    kernel_payload = {
        "ts": str(kernel_state.get("latest_ts") or latest_ts or ""),
        "geo": str(geo_profile or ""),
        "event_kernel_v1": {
            "window": int(kernel_state.get("window") or 0),
            "tags": list(kernel_state.get("tags") or []),
            "top_domains": list(kernel_state.get("top_domains") or []),
        },
    }

    persistence_path = derived_dir / f"persistence_v1_{token}.json"
    kernel_path = derived_dir / f"event_kernel_v1_{token}.json"
    persistence_path.write_text(
        json.dumps(persistence_payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    kernel_path.write_text(
        json.dumps(kernel_payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return str(persistence_path), str(kernel_path)


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
                   geo_profile,geo_factor,tw_rank_score,geo_factor_explain_json,tw_rank_explain_json,domains,L3_domains,max_event_level
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
    series_rows = []
    for r in rows:
        geo_profile = str(r[12] or "") if has_geo else ""
        geo_factor = float(r[13] or 0.0) if has_geo else 0.0
        tw_rank_score = float(r[14] or 0.0) if has_geo else float(r[10] or 0.0)
        geo_raw = str(r[15] or "{}") if has_geo else "{}"
        tw_raw = str(r[16] or "{}") if has_geo else "{}"
        domains = int(r[17] or 0) if has_geo else int(r[12] or 0)
        l3_domains = int(r[18] or 0) if has_geo else int(r[13] or 0)
        max_event_level = str(r[19] or "L1") if has_geo else str(r[14] or "L1")

        geo_obj, geo_text, _ = parse_explain_payload(geo_raw)
        _, tw_text, _ = parse_explain_payload(tw_raw)
        gate = "unknown"
        if isinstance(geo_obj, dict):
            gate_obj = geo_obj.get("gate")
            if isinstance(gate_obj, dict):
                passed = gate_obj.get("passed")
                if passed is True:
                    gate = "true"
                elif passed is False:
                    gate = "false"

        series_rows.append(
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
                "geo_profile": geo_profile,
                "geo_factor": geo_factor,
                "tw_rank_score": tw_rank_score,
                "geo_gate": gate,
                "geo_explain_text": geo_text,
                "tw_explain_text": tw_text,
                "domains": domains,
                "L3_domains": l3_domains,
                "max_event_level": max_event_level,
            }
        )
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


def render(cfg, latest_ts, domains, events, chains, top3, persistence_state, kernel_state):
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
.chain-controls{display:flex;gap:10px;flex-wrap:wrap;margin:10px 0 12px}
.chain-controls label{font-size:12px;color:#444;display:flex;align-items:center;gap:6px}
.chain-controls select{padding:4px 8px;border:1px solid #ccc;border-radius:8px;background:#fff}
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
.geo-col details{margin:4px 0}
.geo-col summary{cursor:pointer;font-size:12px;color:#1f2937}
.geo-col pre{max-height:180px;overflow:auto;background:#f8fafc;border:1px solid #e5e7eb;border-radius:8px;padding:8px;font-size:11px;line-height:1.35}
body.geo-off .geo-col{display:none}
.pers-note{font-size:12px;color:#4b5563;margin:0 0 8px}
.pers-table td,.pers-table th{font-size:12px}
.ers-badge{display:inline-block;padding:2px 8px;border-radius:999px;font-size:11px;border:1px solid #d1d5db}
.ers-watch{background:#fff7ed;border-color:#fdba74;color:#9a3412}
.ers-eligible{background:#ecfeff;border-color:#67e8f9;color:#155e75}
.kernel-muted{font-size:11px;color:#6b7280}
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

    persistence_tags = list((persistence_state or {}).get("tags") or [])
    kernel_tags = {}
    for row in list((kernel_state or {}).get("tags") or []):
        tag = str(row.get("tag") or "")
        if tag:
            kernel_tags[tag] = list(row.get("top_domains") or [])

    observed_tags = [
        t for t in persistence_tags if str(t.get("ers") or "none") in ("watch", "eligible")
    ][:3]
    html.append("<div class='card'><h3>Persistence (Observation)</h3>")
    html.append(
        "<p class='pers-note'>Observation-only. Not used in scoring or gating.</p>"
    )
    if not observed_tags:
        html.append("<span class='muted'>none</span>")
    else:
        html.append("<table class='pers-table'><thead><tr>")
        html.append(
            "<th>tag</th><th>ΔT now</th><th>p</th><th>streak</th><th>dir</th><th>ers</th><th>Top domains (explanatory)</th>"
        )
        html.append("</tr></thead><tbody>")
        for row in observed_tags:
            tag = str(row.get("tag") or "")
            domains_top = kernel_tags.get(tag) or []
            if domains_top:
                domain_text = " / ".join(
                    [f"{str(x.get('domain') or '')} ({float(x.get('kernel') or 0.0):.3f})" for x in domains_top]
                )
            else:
                domain_text = "n/a"
            ers = str(row.get("ers") or "none")
            ers_class = "ers-watch" if ers == "watch" else "ers-eligible"
            html.append(
                "<tr>"
                f"<td>{escape(tag)}</td>"
                f"<td>{float(row.get('delta') or 0.0):+.4f}</td>"
                f"<td>{float(row.get('p') or 0.0):.4f}</td>"
                f"<td>{int(row.get('streak') or 0)}</td>"
                f"<td>{escape(str(row.get('dir') or '0'))}</td>"
                f"<td><span class='ers-badge {ers_class}'>{escape(ers)}</span></td>"
                f"<td><span class='kernel-muted'>{escape(domain_text)}</span></td>"
                "</tr>"
            )
        html.append("</tbody></table>")
    html.append("</div>")

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

    profiles = sorted({str(c.get("geo_profile") or "").strip() for c in chains if str(c.get("geo_profile") or "").strip()})
    profile_opts = ["<option value='all'>all</option>"]
    profile_opts.extend(
        [f"<option value='{escape(p.lower())}'>{escape(p)}</option>" for p in profiles]
    )

    html.append("<div class='card'><h3>鏈式列表</h3>")
    html.append(
        "<div class='chain-controls'>"
        "<label><input id='geoColsToggle' type='checkbox' checked>Show geo columns</label>"
        f"<label>Profile<select id='profileFilter'>{''.join(profile_opts)}</select></label>"
        "<label>Gate<select id='gateFilter'><option value='all'>all</option><option value='true'>gate=true</option><option value='false'>gate=false</option></select></label>"
        "<label><input id='geoPositiveOnly' type='checkbox'>Only geo_factor&gt;0</label>"
        "<label>Sort<select id='chainSort'>"
        "<option value='default'>default</option>"
        "<option value='tw_rank_score_desc'>tw_rank_score desc</option>"
        "<option value='geo_factor_desc'>geo_factor desc</option>"
        "<option value='boosted_push_desc'>boosted_push desc</option>"
        "</select></label>"
        "</div>"
    )
    html.append("<table id='chainTable'><thead><tr>")
    html.append(
        "<th>series</th><th>W_avg</th><th>W_proj</th><th>base</th><th>boosted</th><th>delta</th>"
        "<th class='geo-col'>geo_profile</th><th class='geo-col'>geo_factor</th><th class='geo-col'>tw_rank</th>"
        "<th>top_src</th><th>L3</th><th class='geo-col'>explain</th><th>Top-3</th>"
    )
    html.append("</tr></thead><tbody>")
    for idx, c in enumerate(chains):
        sid = escape(c["series"])
        row_id = f"top3_{sid.replace('.', '_').replace('-', '_')}"
        lvl = escape(c["max_event_level"])
        geo_profile = str(c.get("geo_profile") or "")
        geo_gate = str(c.get("geo_gate") or "unknown")
        html.append(
            f"<tr class='chain-main' data-level='{lvl}' data-default-index='{idx}' "
            f"data-geo-profile='{escape(geo_profile.lower())}' data-geo-factor='{c['geo_factor']:.12f}' "
            f"data-gate='{escape(geo_gate.lower())}' data-tw-rank='{c['tw_rank_score']:.12f}' "
            f"data-boosted-push='{c['boosted_push']:.12f}' data-top3-id='{row_id}'>"
            f"<td>{sid}</td>"
            f"<td>{c['W_avg']:.3f}</td>"
            f"<td>{c['W_proj']:.3f}</td>"
            f"<td>{c['base_push']:.4f}</td>"
            f"<td>{c['boosted_push']:.4f}</td>"
            f"<td>{c['delta_boost']:.4f}</td>"
            f"<td class='geo-col'>{escape(geo_profile or '-')}</td>"
            f"<td class='geo-col'>{c['geo_factor']:.4f}</td>"
            f"<td class='geo-col'>{c['tw_rank_score']:.4f}</td>"
            f"<td>{escape(c['top_src'])}</td>"
            f"<td>{c['L3_domains']}</td>"
            f"<td class='geo-col'>"
            f"<details><summary>Geo explain</summary><pre>{escape(c['geo_explain_text'])}</pre></details>"
            f"<details><summary>TW explain</summary><pre>{escape(c['tw_explain_text'])}</pre></details>"
            f"</td>"
            f"<td><button class='toggle' data-target='{row_id}'>Top-3</button></td>"
            "</tr>"
        )
        html.append(f"<tr class='top3' id='{row_id}' data-level='{lvl}'><td colspan='13'>")
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
const tables = ['domainTable','eventTable'];
const geoColsToggle = document.getElementById('geoColsToggle');
const profileFilter = document.getElementById('profileFilter');
const gateFilter = document.getElementById('gateFilter');
const geoPositiveOnly = document.getElementById('geoPositiveOnly');
const chainSort = document.getElementById('chainSort');
let levelMode = 'all';

function parseNum(value){
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

function toggleGeoColumns(){
  if(!geoColsToggle) return;
  document.body.classList.toggle('geo-off', !geoColsToggle.checked);
}

function applyNonChainTables(){
  tables.forEach(id=>{
    document.querySelectorAll(`#${id} tbody tr`).forEach(tr=>{
      const lvl = (tr.dataset.level || 'L1').toUpperCase();
      tr.style.display = (levelMode==='l3' && lvl!=='L3') ? 'none' : '';
    });
  });
}

function getChainRows(){
  return [...document.querySelectorAll('#chainTable tbody tr.chain-main')];
}

function matchChainFilters(tr){
  const lvl = (tr.dataset.level || 'L1').toUpperCase();
  if(levelMode==='l3' && lvl!=='L3') return false;

  const profile = (tr.dataset.geoProfile || '').toLowerCase();
  const selectedProfile = ((profileFilter && profileFilter.value) || 'all').toLowerCase();
  if(selectedProfile !== 'all' && profile !== selectedProfile) return false;

  const gate = (tr.dataset.gate || 'unknown').toLowerCase();
  const selectedGate = ((gateFilter && gateFilter.value) || 'all').toLowerCase();
  if(selectedGate === 'true' && gate !== 'true') return false;
  if(selectedGate === 'false' && gate !== 'false') return false;

  if(geoPositiveOnly && geoPositiveOnly.checked){
    const g = parseNum(tr.dataset.geoFactor);
    if(!(g !== null && g > 0)) return false;
  }
  return true;
}

function byDefaultIndex(a,b){
  return Number(a.dataset.defaultIndex || 0) - Number(b.dataset.defaultIndex || 0);
}

function sortVisibleRows(rows){
  const mode = (chainSort && chainSort.value) || 'default';
  if(mode === 'default') return [...rows].sort(byDefaultIndex);

  const metricKey = {
    tw_rank_score_desc: 'twRank',
    geo_factor_desc: 'geoFactor',
    boosted_push_desc: 'boostedPush'
  }[mode];
  if(!metricKey) return [...rows].sort(byDefaultIndex);

  return [...rows].sort((a,b)=>{
    const av = parseNum(a.dataset[metricKey]);
    const bv = parseNum(b.dataset[metricKey]);
    if(av === null && bv === null) return byDefaultIndex(a,b);
    if(av === null) return 1;
    if(bv === null) return -1;
    if(av === bv) return byDefaultIndex(a,b);
    return bv - av;
  });
}

function applyChainView(){
  const tbody = document.querySelector('#chainTable tbody');
  if(!tbody) return;
  const rows = getChainRows();
  const visible = [];
  const hidden = [];

  rows.forEach(tr=>{
    const show = matchChainFilters(tr);
    tr.style.display = show ? '' : 'none';
    if(show) visible.push(tr); else hidden.push(tr);
    const top3 = document.getElementById(tr.dataset.top3Id || '');
    if(top3 && !show) top3.style.display = 'none';
  });

  const visibleSorted = sortVisibleRows(visible);
  const hiddenSorted = [...hidden].sort(byDefaultIndex);
  [...visibleSorted, ...hiddenSorted].forEach(tr=>{
    tbody.appendChild(tr);
    const top3 = document.getElementById(tr.dataset.top3Id || '');
    if(top3) tbody.appendChild(top3);
  });
}

function applyAllViews(){
  applyNonChainTables();
  applyChainView();
}

btns.forEach(b=>b.addEventListener('click',()=>{
  btns.forEach(x=>x.classList.remove('active'));
  b.classList.add('active');
  levelMode = b.dataset.mode || 'all';
  applyAllViews();
}));
if(geoColsToggle) geoColsToggle.addEventListener('change', ()=>{
  toggleGeoColumns();
  applyChainView();
});
if(profileFilter) profileFilter.addEventListener('change', applyChainView);
if(gateFilter) gateFilter.addEventListener('change', applyChainView);
if(geoPositiveOnly) geoPositiveOnly.addEventListener('change', applyChainView);
if(chainSort) chainSort.addEventListener('change', applyChainView);
document.querySelectorAll('.toggle').forEach(b=>b.addEventListener('click',()=>{
  const row = document.getElementById(b.dataset.target);
  if(!row) return;
  const main = b.closest('tr.chain-main');
  if(main && main.style.display === 'none') return;
  row.style.display = (row.style.display==='table-row') ? 'none' : 'table-row';
}));
toggleGeoColumns();
applyAllViews();
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
    persistence_cfg = load_persistence_config()
    delta_series_by_tag = build_delta_series_from_db(cur, persistence_cfg)
    persistence_state = compute_tag_persistence(delta_series_by_tag, persistence_cfg)
    persistence_latest_ts = str(persistence_state.get("latest_ts") or latest_ts)
    kernel_state = compute_event_kernel(cur, persistence_latest_ts, persistence_cfg)
    con.close()

    geo_profile = str(chains[0].get("geo_profile") or "unknown") if chains else "unknown"
    write_persistence_outputs(cfg, latest_ts, geo_profile, persistence_state, kernel_state)

    html = render(
        cfg,
        latest_ts,
        domains,
        events,
        chains,
        top3,
        persistence_state,
        kernel_state,
    )
    with open(cfg["out_html"], "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Wrote {cfg['out_html']}")


if __name__ == "__main__":
    main()
