import json, sqlite3
from datetime import datetime, timezone

DB_PATH = "radar.db"
IN_PATH = "output/events_derived.jsonl"

def main():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    # 確保表存在
    cur.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='events_v01'")

    n = 0
    with open(IN_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            ev = json.loads(line)

            date = ev.get("date")
            domain = ev.get("domain")
            series = ev.get("series") or "unmapped"
            event_type = ev.get("type") or "unknown"
            req_key = ev.get("req_key") or "dns_total"

            baseline_avg = float(ev.get("baseline_avg") or 0.0)
            current = float(ev.get("current") or 0.0)
            delta = float(ev.get("delta") or (current - baseline_avg))
            ratio = float(ev.get("ratio") or (current / baseline_avg if baseline_avg else 0.0))

            origin_served = ev.get("origin_served")
            cf_served = ev.get("cf_served")
            dns_total = ev.get("dns_total")  # optional
            strength = ev.get("strength") or ""
            series_raw = ev.get("series_raw") or ""

            # ts: 用 date 當天 00:00Z 也行
            ts = ev.get("ts") or (date + "T00:00:00Z")
            if not date:
                # fallback: now
                date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

            cur.execute("""
                INSERT INTO events_v01
                (ts, date, domain, series, event_type, req_key, baseline_avg, current, delta, ratio,
                origin_served, cf_served, strength, series_raw)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
            ts, date, domain, series, event_type, req_key, baseline_avg, current, delta, ratio,
            origin_served, cf_served, strength, series_raw
      ))


    con.commit()
    con.close()
    print(f"✅ inserted events: {n}")

if __name__ == "__main__":
    main()
