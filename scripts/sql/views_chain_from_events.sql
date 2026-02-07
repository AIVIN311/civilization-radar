-- scripts/sql/views_chain_from_events.sql

BEGIN;

-- 將每日事件變成 series 的「事件強度」：用 ratio 或 delta 作為強度
CREATE VIEW IF NOT EXISTS v01_series_event_strength_daily AS
SELECT
  date,
  series,
  -- 強度：你可以用 ratio_max 或 delta_sum；我先給兩個
  MAX(ratio) AS ratio_peak,
  SUM(delta) AS delta_sum,
  COUNT(*) AS events_n
FROM events_v01
GROUP BY date, series;

-- 共振邊：同一天兩個 series 都有事件，就形成一條邊（undirected）
-- share = 共同出現天數（或權重化共振）
CREATE VIEW IF NOT EXISTS v01_chain_edges_from_events AS
WITH pairs AS (
  SELECT
    a.date AS date,
    a.series AS src_series,
    b.series AS dst_series,
    -- 共振權重：兩者峰值倍率的幾何平均（避免單邊爆炸）
    ( (a.ratio_peak * b.ratio_peak) ) AS co_weight,
    a.ratio_peak AS src_peak,
    b.ratio_peak AS dst_peak
  FROM v01_series_event_strength_daily a
  JOIN v01_series_event_strength_daily b
    ON a.date = b.date
   AND a.series < b.series  -- 去重、避免 self-loop
)
SELECT
  src_series,
  dst_series,
  COUNT(*) AS co_days,
  AVG(co_weight) AS share,
  MAX(src_peak) AS src_peak_max,
  MAX(dst_peak) AS dst_peak_max
FROM pairs
GROUP BY src_series, dst_series
ORDER BY share DESC, co_days DESC;

COMMIT;
