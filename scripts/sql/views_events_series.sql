-- scripts/sql/views_events_series.sql

BEGIN;

-- 每日 series 的事件聚合（同一天同系列發生多少事、平均倍率、最大倍率等）
CREATE VIEW IF NOT EXISTS v01_series_events_daily AS
SELECT
  date,
  series,
  COUNT(*) AS events_n,
  SUM(CASE WHEN event_type='spike' THEN 1 ELSE 0 END) AS spike_n,
  SUM(CASE WHEN event_type='drop'  THEN 1 ELSE 0 END) AS drop_n,
  AVG(ratio) AS ratio_avg,
  MAX(ratio) AS ratio_max,
  SUM(delta) AS delta_sum,
  GROUP_CONCAT(domain, ', ') AS domains_csv
FROM events_v01
GROUP BY date, series;

-- 最新一天的 series 事件態勢（給 dashboard 用）
CREATE VIEW IF NOT EXISTS v01_series_events_latest AS
WITH mx AS (SELECT MAX(date) AS date FROM events_v01)
SELECT
  e.date,
  e.series,
  e.events_n,
  e.spike_n,
  e.drop_n,
  e.ratio_avg,
  e.ratio_max,
  e.delta_sum,
  e.domains_csv
FROM v01_series_events_daily e
JOIN mx ON mx.date = e.date
ORDER BY e.ratio_max DESC, e.events_n DESC;

COMMIT;
