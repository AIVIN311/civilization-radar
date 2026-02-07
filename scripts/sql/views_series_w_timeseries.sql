-- scripts/sql/views_series_w_timeseries.sql

BEGIN;

-- series 每個 ts 的平均 W（domain 層聚合）
CREATE VIEW IF NOT EXISTS v02_series_w_ts AS
SELECT
  ts,
  series,
  AVG(W) AS W_avg,
  COUNT(*) AS domains_n
FROM metrics_v02
GROUP BY ts, series;

COMMIT;
