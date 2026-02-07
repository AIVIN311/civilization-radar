BEGIN;

CREATE TABLE IF NOT EXISTS events_v01 (
  id                    INTEGER PRIMARY KEY AUTOINCREMENT,
  ts                    TEXT NOT NULL,
  date                  TEXT NOT NULL,
  domain                TEXT NOT NULL,
  series                TEXT NOT NULL,
  event_type            TEXT NOT NULL,
  req_key               TEXT NOT NULL,
  baseline_avg          REAL NOT NULL,
  current               REAL NOT NULL,
  delta                 REAL NOT NULL,
  ratio                 REAL NOT NULL,
  origin_served         INTEGER,
  cf_served             INTEGER,
  dns_total             INTEGER,
  strength              REAL,
  series_raw            TEXT,
  event_level           TEXT DEFAULT 'L1',
  matched_signals_json  TEXT DEFAULT '[]',
  strength_explain_json TEXT DEFAULT '{}',
  sig                   TEXT,
  matched_json          TEXT,
  source                TEXT DEFAULT 'derived_daily',
  created_at            TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_events_v01_dedup
ON events_v01(date, domain, event_type, req_key);

CREATE INDEX IF NOT EXISTS ix_events_v01_date ON events_v01(date);
CREATE INDEX IF NOT EXISTS ix_events_v01_series ON events_v01(series);
CREATE INDEX IF NOT EXISTS ix_events_v01_domain ON events_v01(domain);
CREATE INDEX IF NOT EXISTS ix_events_v01_ratio ON events_v01(ratio);

COMMIT;
