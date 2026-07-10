"""Descriptive-only Taiwan market/Radar overlay analysis."""
from __future__ import annotations
import argparse, math
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from common import pearson, read_csv, spearman, write_csv, write_json


def quantile(values, q):
    values=sorted(values); pos=(len(values)-1)*q; lo=int(pos); hi=min(lo+1,len(values)-1); return values[lo]+(values[hi]-values[lo])*(pos-lo)


def market_features(rows):
    by_symbol=defaultdict(list)
    for row in rows: by_symbol[row["symbol"]].append(row)
    out={}
    for symbol,items in by_symbol.items():
        items.sort(key=lambda r:r["date"]); closes=[]; returns=[]
        for i,row in enumerate(items):
            close=float(row["close"]); closes.append(close); ret=math.log(close/closes[-2]) if i else None; returns.append(ret)
            result=dict(row); result["log_return_1d"]=ret; result["abs_return"]=abs(ret) if ret is not None else None
            for window in (5,20):
                sample=[x for x in returns[max(1,i-window+1):i+1] if x is not None]
                result[f"rv{window}"]=math.sqrt(252*sum((x-sum(sample)/len(sample))**2 for x in sample)/(len(sample)-1)) if len(sample)>=window else None
            peak=max(closes[max(0,i-19):i+1]); result["drawdown20"]=close/peak-1; out[(row["date"],symbol)]=result
    return out


def align_event(event, trading_dates):
    raw=event["datetime_local"]
    dt=datetime.fromisoformat(raw) if "T" in raw else datetime.fromisoformat(raw+"T23:59:00+08:00")
    d=dt.date().isoformat(); after=dt.hour>=13 and (dt.hour>13 or dt.minute>=30)
    choices=[x for x in trading_dates if x>d or (x==d and not after)]
    return choices[0] if choices else None


def analyze(market_csv,radar_csv,events_csv,output_dir,start,end):
    output_dir=Path(output_dir); market=market_features(read_csv(market_csv)); radar={r["date"]:r for r in read_csv(radar_csv)}
    dates=sorted(d for d in radar if start<=d<=end and (d,"TAIEX") in market and (d,"2330") in market)
    rv=[market[(d,"TAIEX")]["rv20"] for d in dates if market[(d,"TAIEX")]["rv20"] is not None]; q1=quantile(rv,1/3) if rv else None; q2=quantile(rv,2/3) if rv else None
    fields=list(next(iter(radar.values())).keys())+["taiex_close","taiex_log_return_1d","taiex_abs_return","taiex_rv5","taiex_rv20","taiex_drawdown20","2330_close","2330_log_return_1d","2330_abs_return","2330_rv5","2330_rv20","2330_drawdown20","regime"]
    aligned=[]
    for d in dates:
        row=dict(radar[d]); t=market[(d,"TAIEX")]; s=market[(d,"2330")]
        for prefix,item in (("taiex",t),("2330",s)):
            for src,dst in (("close","close"),("log_return_1d","log_return_1d"),("abs_return","abs_return"),("rv5","rv5"),("rv20","rv20"),("drawdown20","drawdown20")): row[f"{prefix}_{dst}"]=item[src]
        row["regime"]="warmup" if t["rv20"] is None else "quiet" if t["rv20"]<=q1 else "normal" if t["rv20"]<=q2 else "stressed"; aligned.append(row)
    write_csv(output_dir/"aligned_daily.csv",fields,aligned)
    radar_fields=[x for x in radar[dates[0]] if x!="date"] if dates else []
    relationships=[]
    for rf in radar_fields:
        for target in ("taiex_log_return_1d","taiex_abs_return","taiex_rv20","2330_log_return_1d","2330_abs_return"):
            pairs=[(float(r[rf]),float(r[target])) for r in aligned if r.get(rf) not in (None,"") and r.get(target) not in (None,"")]
            xs=[x for x,y in pairs]; ys=[y for x,y in pairs]; mid=len(pairs)//2; rho=spearman(xs,ys) if len(pairs)>=3 else None
            halves=[spearman(xs[:mid],ys[:mid]),spearman(xs[mid:],ys[mid:])] if mid>=3 else [None,None]
            stable=rho is not None and abs(rho)>=.30 and None not in halves and halves[0]*halves[1]>0
            relationships.append({"radar_feature":rf,"market_feature":target,"n":len(pairs),"pearson":pearson(xs,ys),"spearman":rho,"first_half_spearman":halves[0],"second_half_spearman":halves[1],"label":"relationship_candidate" if len(pairs)>=60 and stable else "insufficient_data" if len(pairs)<60 else "descriptive_only"})
    lags=[]
    for lag in range(-5,6):
        for rf in radar_fields:
            pairs=[]
            for i,row in enumerate(aligned):
                j=i+lag
                if 0<=j<len(aligned) and aligned[j].get("taiex_log_return_1d") not in (None,""): pairs.append((float(row[rf]),float(aligned[j]["taiex_log_return_1d"])))
            lags.append({"radar_feature":rf,"market_feature":"taiex_log_return_1d","lag_trading_days":lag,"n":len(pairs),"spearman":spearman([x for x,y in pairs],[y for x,y in pairs]) if len(pairs)>=3 else None})
    events=[]
    for event in read_csv(events_csv):
        d=align_event(event,dates)
        if d:
            i=dates.index(d); window=[]
            for offset in range(-3,4):
                if 0<=i+offset<len(dates): window.append({"offset":offset,"date":dates[i+offset],"taiex_log_return_1d":market[(dates[i+offset],"TAIEX")]["log_return_1d"]})
            events.append({**event,"aligned_trading_date":d,"window":window})
    counts=dict(__import__('collections').Counter(e["event_type"] for e in events))
    result={"status":"insufficient_data" if len(dates)<60 else "complete","language_contract":"descriptive_only_no_causality_or_forecast","window":{"start":start,"end":end,"effective_trading_days":len(dates)},"regime_thresholds":{"quiet_max_rv20":q1,"normal_max_rv20":q2},"relationships":relationships,"lags":lags,"events":events,"event_type_counts":counts,"event_type_evaluation":{k:("descriptive_only" if v>=5 else "display_only") for k,v in counts.items()}}
    write_json(output_dir/"analysis.json",result)
    candidates=[r for r in relationships if r["label"]=="relationship_candidate"]
    report="# 台股情境疊圖 v0.1\n\n此報告只描述 overlap、association、regime 與 event window；不宣稱因果，也不提供投資預測。\n\n"
    report+=f"- 分析窗口：{start} 至 {end}\n- 有效交易日：{len(dates)}\n- 判讀狀態：{result['status']}\n- relationship candidates：{len(candidates)}\n\n"
    report+="## Regime\n\nTAIEX 20 日 realized volatility 的樣本內三分位用於 quiet／normal／stressed 分組。\n"
    (output_dir/"report.md").write_text(report,encoding="utf-8")
    try:
        import matplotlib.pyplot as plt
        plt.figure(figsize=(11,5)); plt.plot(dates,[float(market[(d,"TAIEX")]["close"]) for d in dates],label="TAIEX"); plt.legend(); plt.tight_layout(); plt.savefig(output_dir/"taiex_overlay.png",dpi=140); plt.close(); chart="PASS"
    except ImportError: chart="WARN:matplotlib_missing"
    result["chart_status"]=chart; write_json(output_dir/"analysis.json",result); return result


def main():
    p=argparse.ArgumentParser();
    for n in ("market","radar","events","output-dir","start","end"): p.add_argument(f"--{n}",required=True)
    a=p.parse_args(); analyze(a.market,a.radar,a.events,getattr(a,"output_dir"),a.start,a.end)
if __name__ == "__main__": main()
