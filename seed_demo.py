import sqlite3, time
DB="radar.db"

conn=sqlite3.connect(DB)

conn.executescript(open("schema.sql","r",encoding="utf-8").read())

now = int(time.time())
slot = now - (now % 1800)  # 對齊 30m

rows = [
  ("algorithmiclegitimacy.com", slot, 120, 50000, 8, 0, 2, 0, 0.9, "Hong Kong", 60, "United States", 25, "other"),
  ("algorithmicallocation.com", slot, 260, 88000, 40, 1, 50, 4, 0.95, "France", 110, "Russian Federation", 95, "env_scan"),
  ("civilizationcaching.com", slot, 55, 12000, 2, 0, 0, 0, 0.7, "Netherlands", 20, "United States", 10, "other"),
]

for r in rows:
    conn.execute("""INSERT OR REPLACE INTO metrics_30m(
      domain, ts, requests_total, bandwidth_bytes, http_4xx, http_5xx, cf_mitigated, cf_challenged,
      bot_like_ratio, top_country_1, top_country_1_requests, top_country_2, top_country_2_requests, top_sig
    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", r)

conn.commit()
print("seeded")
