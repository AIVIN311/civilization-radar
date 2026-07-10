"""Validate context inputs and emit a machine-readable receipt."""
from __future__ import annotations
import argparse, json
from collections import defaultdict
from pathlib import Path
from common import read_csv, read_json, sha256, write_json


def duplicate_check(rows, keys, numeric):
    seen={}; identical=conflicts=0
    for row in rows:
        key=tuple(row.get(k) for k in keys); value=tuple(row.get(k) for k in numeric)
        if key in seen:
            if seen[key] == value: identical += 1
            else: conflicts += 1
        else: seen[key]=value
    return identical,conflicts


def validate(market, radar, snapshots, events, mapping, output, expected_symbols):
    failures=[]; warnings=[]; market_rows=read_csv(market); radar_rows=read_csv(radar)
    same,conflict=duplicate_check(market_rows,["date","symbol"],["open","high","low","close","volume"])
    if same: warnings.append(f"market_identical_duplicates:{same}")
    if conflict: failures.append(f"market_conflicting_duplicates:{conflict}")
    for i,row in enumerate(market_rows,2):
        try:
            o,h,l,c=[float(row[k]) for k in ("open","high","low","close")]
            if l>min(o,c) or h<max(o,c) or l>h: failures.append(f"invalid_ohlc:line_{i}")
        except (ValueError,TypeError): failures.append(f"missing_ohlc:line_{i}")
    present=defaultdict(set)
    for row in market_rows: present[row["symbol"]].add(row["date"][:7])
    all_months=set().union(*present.values()) if present else set()
    for symbol in expected_symbols:
        if symbol not in present: failures.append(f"missing_symbol:{symbol}")
        missing=sorted(all_months-present.get(symbol,set()))
        if missing: failures.append(f"missing_historical_months:{symbol}:{','.join(missing)}")
    bad_json=[]; snapshot_rows=[]
    with Path(snapshots).open(encoding="utf-8-sig") as handle:
        for n,line in enumerate(handle,1):
            try: snapshot_rows.append(json.loads(line))
            except Exception: bad_json.append(n)
    if bad_json: failures.append(f"bad_snapshot_json:{len(bad_json)}")
    same,conflict=duplicate_check(snapshot_rows,["date","domain"],["dns_total","cf_served","origin_served"])
    if same: warnings.append(f"snapshot_identical_duplicates:{same}")
    if conflict: failures.append(f"snapshot_conflicting_duplicates:{conflict}")
    mapped=read_json(mapping); unknown=sorted({r.get("domain","").lower() for r in snapshot_rows if r.get("domain","").lower() not in mapped})
    if unknown: warnings.append(f"unknown_domains:{len(unknown)}")
    fingerprints={name:sha256(path) for name,path in {
        "market_daily.csv":market,"radar_daily_features.csv":radar,"snapshots":snapshots,
        "macro_events.csv":events,"series_map.json":mapping}.items()}
    result={"status":"FAIL" if failures else "WARN" if warnings else "PASS","failures":failures,"warnings":warnings,"unknown_domains":unknown,"counts":{"market_rows":len(market_rows),"radar_days":len(radar_rows)},"sha256":fingerprints}
    write_json(output,result); return result


def main():
    p=argparse.ArgumentParser();
    for name in ("market","radar","snapshots","events","mapping","output"): p.add_argument(f"--{name}",required=True)
    p.add_argument("--symbols",default="TAIEX,2330"); a=p.parse_args(); result=validate(a.market,a.radar,a.snapshots,a.events,a.mapping,a.output,a.symbols.split(",")); raise SystemExit(result["status"]=="FAIL")
if __name__ == "__main__": main()
