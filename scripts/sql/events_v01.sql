-- scripts/sql/events_v01.sql
-- Purpose: store derived events from daily_snapshots.jsonl (or other sources)

BEGIN;

CREATE TABLE IF NOT EXISTS events_v01 (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  ts            TEXT NOT NULL,   -- ISO8601 timestamp or date (use date at minimum)
  date          TEXT NOT NULL,   -- YYYY-MM-DD (for daily events)
  domain        TEXT NOT NULL,
  series        TEXT NOT NULL,   -- series_map resolved or 'unmapped'
  event_type    TEXT NOT NULL,   -- e.g. spike, drop, anomaly, l3_event, etc.
  req_key       TEXT NOT NULL,   -- dns_total | cf_served | origin_served ...
  baseline_avg  REAL NOT NULL,
  current       REAL NOT NULL,
  delta         REAL NOT NULL,
  ratio         REAL NOT NULL,

  -- optional context (keep nullable for forward-compat)
  origin_served INTEGER,
  cf_served     INTEGER,
  dns_total     INTEGER,

  -- optional: allow attaching matched signals / signatures later
  sig           TEXT,
  matched_json  TEXT,

  -- provenance / versioning
  source        TEXT DEFAULT 'derived_daily',  -- derived_daily / cf_log / manual / etc.
  created_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

-- Prevent duplicate insert when you re-run loaders:
-- unique by (date, domain, event_type, req_key)
CREATE UNIQUE INDEX IF NOT EXISTS ux_events_v01_dedup
ON events_v01(date, domain, event_type, req_key);

CREATE INDEX IF NOT EXISTS ix_events_v01_date ON events_v01(date);
CREATE INDEX IF NOT EXISTS ix_events_v01_series ON events_v01(series);
CREATE INDEX IF NOT EXISTS ix_events_v01_domain ON events_v01(domain);
CREATE INDEX IF NOT EXISTS ix_events_v01_ratio ON events_v01(ratio);

COMMIT;
