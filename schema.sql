CREATE TABLE IF NOT EXISTS domains (
  domain TEXT PRIMARY KEY,
  series TEXT,
  url TEXT
);

CREATE TABLE IF NOT EXISTS metrics_30m (
  domain TEXT,
  ts INTEGER,                 -- unix epoch seconds
  requests_total INTEGER,
  bandwidth_bytes INTEGER,
  http_4xx INTEGER,
  http_5xx INTEGER,
  cf_mitigated INTEGER,
  cf_challenged INTEGER,
  bot_like_ratio REAL,
  top_country_1 TEXT,
  top_country_1_requests INTEGER,
  top_country_2 TEXT,
  top_country_2_requests INTEGER,
  top_sig TEXT,               -- 例如 env_scan/admin_probe/wp_scan/other
  PRIMARY KEY (domain, ts)
);
