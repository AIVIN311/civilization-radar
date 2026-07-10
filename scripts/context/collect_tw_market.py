"""Collect monthly TWSE TAIEX and stock data into a reproducible context CSV."""
from __future__ import annotations

import argparse, json, ssl, time, urllib.request
from datetime import date, datetime, timezone
from pathlib import Path
from common import iso_date, parse_number, read_json, utc_now, write_csv, write_json

BASE = "https://www.twse.com.tw/rwd/zh"


def months(start, end):
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        yield f"{y:04d}{m:02d}01"
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)


def fetch(url, timeout=30, retries=3, throttle=1.0):
    errors = []
    tls = ssl.create_default_context()
    # Python 3.13 enables strict X.509 checks that reject part of TWSE's otherwise
    # trusted chain for a missing legacy extension. Keep hostname/CA validation.
    if hasattr(ssl, "VERIFY_X509_STRICT"):
        tls.verify_flags &= ~ssl.VERIFY_X509_STRICT
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent":"civilization-radar-context/0.1"})
            with urllib.request.urlopen(req, timeout=timeout, context=tls) as response:
                data = json.loads(response.read().decode("utf-8-sig"))
            time.sleep(throttle); return data, attempt
        except Exception as exc:
            errors.append(str(exc))
            if attempt < retries: time.sleep(2 ** (attempt - 1))
    raise RuntimeError(f"TWSE request failed after {retries} attempts: {errors[-1]}")


def table(payload):
    if payload.get("stat") not in (None, "OK"): raise ValueError(f"TWSE status: {payload.get('stat')}")
    fields, rows = payload.get("fields", []), payload.get("data", [])
    return [dict(zip(fields, row)) for row in rows]


def find(row, *needles):
    for key, value in row.items():
        normalized = key.replace(" ", "")
        if any(n in normalized for n in needles): return value
    return None


def collect(start, end, symbols, output, raw_dir, offline=False, timeout=30, retries=3, throttle=1.0):
    output, raw_dir = Path(output), Path(raw_dir); raw_dir.mkdir(parents=True, exist_ok=True)
    all_rows, requests = [], []
    def load_or_fetch(raw, url):
        meta=raw.with_suffix(".meta.json"); attempts=0
        if raw.exists():
            payload=read_json(raw); mode="cache"
            if meta.exists(): retrieved=read_json(meta)["retrieved_utc"]
            else:
                retrieved=datetime.fromtimestamp(raw.stat().st_mtime,timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z")
                write_json(meta,{"retrieved_utc":retrieved,"url":url})
        elif offline: raise FileNotFoundError(f"offline raw response missing: {raw}")
        else:
            payload,attempts=fetch(url,timeout,retries,throttle); retrieved=utc_now(); write_json(raw,payload);write_json(meta,{"retrieved_utc":retrieved,"url":url});mode="live"
        requests.append({"url":url,"raw":str(raw),"mode":mode,"attempts":attempts,"retrieved_utc":retrieved})
        return payload,retrieved
    for month in months(start, end):
        index_close = {}; index_volume = {}
        if "TAIEX" in symbols:
            endpoints = {
                "taiex_ohlc": f"{BASE}/TAIEX/MI_5MINS_HIST?date={month}&response=json",
                "taiex_volume": f"{BASE}/afterTrading/FMTQIK?date={month}&response=json",
            }
            payloads = {}
            for name, url in endpoints.items():
                raw = raw_dir / f"{name}_{month[:6]}.json"
                payload,retrieved=load_or_fetch(raw,url); payloads[name] = payload
            for row in table(payloads["taiex_volume"]):
                d = iso_date(find(row, "日期")); index_volume[d] = parse_number(find(row, "成交股數"))
            for row in table(payloads["taiex_ohlc"]):
                d = iso_date(find(row, "日期")); index_close[d] = row
                vals = [parse_number(find(row, key)) for key in ("開盤", "最高", "最低", "收盤")]
                all_rows.append(dict(zip(
                    ["date","market","symbol","open","high","low","close","volume","source","retrieved_utc"],
                    [d,"TWSE","TAIEX",*vals,index_volume.get(d),endpoints["taiex_ohlc"]+";"+endpoints["taiex_volume"],retrieved])))
        for symbol in [s for s in symbols if s != "TAIEX"]:
            url = f"{BASE}/afterTrading/STOCK_DAY?date={month}&stockNo={symbol}&response=json"
            raw = raw_dir / f"stock_{symbol}_{month[:6]}.json"
            payload,retrieved=load_or_fetch(raw,url)
            for row in table(payload):
                d = iso_date(find(row,"日期")); vals = [parse_number(find(row,k)) for k in ("開盤", "最高", "最低", "收盤")]
                all_rows.append(dict(zip(
                    ["date","market","symbol","open","high","low","close","volume","source","retrieved_utc"],
                    [d,"TWSE",symbol,*vals,parse_number(find(row,"成交股數")),url,retrieved])))
    all_rows.sort(key=lambda r:(r["date"],r["symbol"]))
    write_csv(output,["date","market","symbol","open","high","low","close","volume","source","retrieved_utc"],all_rows)
    return {"requests":requests,"rows":len(all_rows)}


def main():
    p=argparse.ArgumentParser(); p.add_argument("--start",required=True); p.add_argument("--end",required=True); p.add_argument("--symbols",default="TAIEX,2330"); p.add_argument("--output",required=True); p.add_argument("--raw-dir",required=True); p.add_argument("--offline",action="store_true"); p.add_argument("--receipt")
    a=p.parse_args(); result=collect(date.fromisoformat(a.start),date.fromisoformat(a.end),a.symbols.split(","),a.output,a.raw_dir,a.offline)
    if a.receipt: write_json(a.receipt,result)

if __name__ == "__main__": main()
