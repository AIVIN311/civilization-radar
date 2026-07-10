"""Orchestrate a non-canonical, failure-safe market context run."""
from __future__ import annotations
import argparse, shutil, sys, traceback
from datetime import datetime, timezone
from pathlib import Path
from analyze_tw_overlay import analyze
from build_radar_features import build
from collect_tw_market import collect
from common import atomic_replace_dir, sha256, utc_now, write_json
from validate_context import validate


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--start",required=True);p.add_argument("--end",required=True);p.add_argument("--market-start",required=True);p.add_argument("--symbols",default="TAIEX,2330");p.add_argument("--events",required=True);p.add_argument("--output-dir",default="output/context");p.add_argument("--snapshots",default="input/snapshots.jsonl");p.add_argument("--mapping",default="config/series_map.json");p.add_argument("--offline",action="store_true")
    a=p.parse_args(); root=Path(a.output_dir); run_id=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"); run=root/"runs"/run_id; run.mkdir(parents=True,exist_ok=False)
    receipt={"run_id":run_id,"artifact_class":"non_canonical_context","started_utc":utc_now(),"parameters":vars(a),"steps":[],"warnings":[],"status":"RUNNING"}
    try:
        market=run/"market_daily.csv"; raw_cache=root/"raw"
        if not raw_cache.exists() and (root/"latest"/"raw").exists(): shutil.copytree(root/"latest"/"raw",raw_cache)
        cr=collect(__import__('datetime').date.fromisoformat(a.market_start),__import__('datetime').date.fromisoformat(a.end),a.symbols.split(","),market,raw_cache,a.offline)
        shutil.copytree(raw_cache,run/"raw"); receipt["steps"].append({"name":"collect_tw_market","status":"PASS",**cr})
        radar=run/"radar_daily_features.csv"; diag=run/"radar_diagnostics.json"; br=build(a.snapshots,a.mapping,radar,a.start,a.end,diag); receipt["steps"].append({"name":"build_radar_features","status":"PASS","rows":br["rows"]})
        validation=validate(market,radar,a.snapshots,a.events,a.mapping,run/"validation.json",a.symbols.split(",")); receipt["steps"].append({"name":"validate_context","status":validation["status"]}); receipt["warnings"].extend(validation["warnings"])
        if validation["status"]=="FAIL": raise RuntimeError("context validation failed: "+", ".join(validation["failures"][:5]))
        result=analyze(market,radar,a.events,run,a.start,a.end); receipt["steps"].append({"name":"analyze_tw_overlay","status":"PASS","effective_trading_days":result["window"]["effective_trading_days"]})
        if result.get("chart_status","").startswith("WARN"): receipt["warnings"].append(result["chart_status"])
        artifacts=[p for p in run.rglob("*") if p.is_file() and p.name!="run_receipt.json"]
        receipt["artifacts"]={str(p.relative_to(run)):sha256(p) for p in artifacts}; receipt["status"]="PASS"; receipt["finished_utc"]=utc_now(); write_json(run/"run_receipt.json",receipt)
        staging=root/(".latest-"+run_id); shutil.copytree(run,staging); atomic_replace_dir(staging,root/"latest")
        print(f"PASS {run}"); return 0
    except Exception as exc:
        receipt["status"]="FAIL";receipt["failed_step_error"]=str(exc);receipt["traceback"]=traceback.format_exc();receipt["finished_utc"]=utc_now();write_json(run/"run_receipt.json",receipt);print(f"FAIL {run}: {exc}",file=sys.stderr);return 1
if __name__=="__main__": raise SystemExit(main())
