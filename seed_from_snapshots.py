import json
import os
import sqlite3
from datetime import datetime, timezone

DB_PATH = "radar.db"
INPUT_PATH = os.path.join("input", "snapshots.jsonl")

# 以 30 分鐘為一個 slot（你剛剛說 30 分鐘）
SLOT_SECONDS = 30 * 60


def parse_iso(ts: str) -> datetime:
    # 支援像 "2026-02-03T15:30:00+08:00"
    return datetime.fromisoformat(ts)


def to_slot(dt: datetime) -> int:
    # slot = UnixTime // SLOT_SECONDS
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    epoch = int(dt.timestamp())
    return epoch // SLOT_SECONDS


def main():
    if not os.path.exists(INPUT_PATH):
        raise FileNotFoundError(f"Missing {INPUT_PATH}. Create folder 'input' and file 'snapshots.jsonl'.")

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # 建表（如果還沒建立）
    with open("schema_v01.sql", "r", encoding="utf-8") as f:
        cur.executescript(f.read())

    inserted = 0

    with open(INPUT_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            obj = json.loads(line)
            ts = obj["ts"]
            dt = parse_iso(ts)
            slot = to_slot(dt)

            domain = obj["domain"].strip().lower()
            series = (obj.get("series") or "").strip()
            req = int(obj.get("req") or 0)
            mitigated = int(obj.get("mitigated") or 0)
            cf_served = int(obj.get("cf_served") or 0)
            origin_served = int(obj.get("origin_served") or 0)
            sig = (obj.get("sig") or "").strip()
            notes = (obj.get("notes") or "").strip()

            top_countries = obj.get("top_countries") or {}
            top_countries_json = json.dumps(top_countries, ensure_ascii=False)

            cur.execute(
                """
                INSERT INTO snapshot
                (ts, slot, domain, series, req, mitigated, cf_served, origin_served, sig, top_countries_json, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (ts, slot, domain, series, req, mitigated, cf_served, origin_served, sig, top_countries_json, notes),
            )
            inserted += 1

    conn.commit()
    conn.close()

    print(f"seeded_from_snapshots: inserted {inserted} rows into snapshot")


if __name__ == "__main__":
    main()
