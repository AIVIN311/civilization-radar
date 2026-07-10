"""Read snapshots without mutation and build daily Radar context features."""
from __future__ import annotations

import argparse, json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from common import read_json, write_csv, write_json


def snapshot_date(row):
    if row.get("ts"):
        return datetime.fromisoformat(row["ts"].replace("Z","+00:00")).date().isoformat()
    return row["date"]


def build(snapshots, mapping_path, output, start, end, diagnostics=None):
    mapping=read_json(mapping_path); default=mapping.get("default"); by_day=defaultdict(list); bad=[]
    with Path(snapshots).open(encoding="utf-8-sig") as handle:
        for line_no,line in enumerate(handle,1):
            try: row=json.loads(line); d=snapshot_date(row)
            except Exception as exc: bad.append({"line":line_no,"error":str(exc)}); continue
            if start <= d <= end: by_day[d].append(row)
    series=sorted(set(mapping.values())-{default} | {default}); fields=["date","requests_total","domain_count","cache_share","origin_share","top5_share","hhi"]
    fields += [f"series_{s}_requests" for s in series]+[f"series_{s}_share" for s in series]
    rows=[]; unknown=set()
    for d,items in sorted(by_day.items()):
        domain_totals=defaultdict(float); cache=origin=0.0; s_totals=defaultdict(float)
        for item in items:
            domain=item.get("domain","").lower(); req=float(item.get("dns_total",item.get("req",0)) or 0)
            domain_totals[domain]+=req; cache+=float(item.get("cf_served",0) or 0); origin+=float(item.get("origin_served",0) or 0)
            if domain not in mapping: unknown.add(domain)
            s_totals[mapping.get(domain,default)]+=req
        total=sum(domain_totals.values()); traffic=cache+origin
        out={"date":d,"requests_total":total,"domain_count":len(domain_totals),"cache_share":cache/traffic if traffic else 0,"origin_share":origin/traffic if traffic else 0,"top5_share":sum(sorted(domain_totals.values(),reverse=True)[:5])/total if total else 0,"hhi":sum((v/total)**2 for v in domain_totals.values()) if total else 0}
        for s in series: out[f"series_{s}_requests"]=s_totals[s]; out[f"series_{s}_share"]=s_totals[s]/total if total else 0
        rows.append(out)
    write_csv(output,fields,rows)
    result={"rows":len(rows),"bad_json":bad,"unknown_domains":sorted(unknown),"series":series}
    if diagnostics: write_json(diagnostics,result)
    return result


def main():
    p=argparse.ArgumentParser(); p.add_argument("--snapshots",required=True);p.add_argument("--mapping",required=True);p.add_argument("--output",required=True);p.add_argument("--start",required=True);p.add_argument("--end",required=True);p.add_argument("--diagnostics")
    a=p.parse_args(); build(a.snapshots,a.mapping,a.output,a.start,a.end,a.diagnostics)
if __name__ == "__main__": main()
