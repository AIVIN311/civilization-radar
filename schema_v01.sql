-- v0.1 schema (minimal, additive)

CREATE TABLE IF NOT EXISTS snapshot (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  slot INTEGER NOT NULL,
  domain TEXT NOT NULL,
  series TEXT,
  req INTEGER DEFAULT 0,
  mitigated INTEGER DEFAULT 0,
  cf_served INTEGER DEFAULT 0,
  origin_served INTEGER DEFAULT 0,
  sig TEXT,
  top_countries_json TEXT,
  notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_snapshot_slot ON snapshot(slot);
CREATE INDEX IF NOT EXISTS idx_snapshot_domain_slot ON snapshot(domain, slot);
