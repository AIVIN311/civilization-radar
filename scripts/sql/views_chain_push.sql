-- scripts/sql/views_chain_push.sql

BEGIN;

-- 取得每個 series 在每個 ts 的 ΔW（差分）
CREATE VIEW IF NOT EXISTS v02_series_dW_ts AS
WITH ordered AS (
  SELECT
    ts,
    series,
    W_avg,
    LAG(W_avg) OVER (PARTITION BY series ORDER BY ts) AS W_prev
  FROM v02_series_w_ts
)
SELECT
  ts,
  series,
  (W_avg - COALESCE(W_prev, W_avg)) AS dW
FROM ordered;

-- 方向推力：src 用前一格的 dW，dst 用當格的 dW
-- push = AVG( src_dW_prev * dst_dW_now ) over recent window
-- 這是簡化的 lead-lag 力量指標（可用、可視覺化、可迭代）
CREATE VIEW IF NOT EXISTS v03_chain_edges_latest AS
WITH mx AS (SELECT MAX(ts) AS ts FROM v02_series_dW_ts),
-- recent window：最後 16 slots（你 dashboard 用 SPARK_K=16）
win AS (
  SELECT *
  FROM v02_series_dW_ts
  WHERE ts IN (
    SELECT ts FROM v02_series_dW_ts
    ORDER BY ts DESC
    LIMIT 16
  )
),
-- prev shift: src uses lagged ts
shifted AS (
  SELECT
    ts,
    series,
    dW,
    LAG(dW) OVER (PARTITION BY series ORDER BY ts) AS dW_prev
  FROM win
),
pairs AS (
  SELECT
    b.ts AS ts,
    a.series AS src_series,
    b.series AS dst_series,
    (COALESCE(a.dW_prev, 0.0) * COALESCE(b.dW, 0.0)) AS push_raw
  FROM shifted a
  JOIN shifted b
    ON a.ts = b.ts
   AND a.series <> b.series
)
SELECT
  ts,
  dst_series,
  src_series,
  AVG(push_raw) AS push,
  AVG(ABS(push_raw)) AS share,
  COUNT(*) AS edge_n,
  '' AS domain
FROM pairs
WHERE ts = (SELECT ts FROM mx)
GROUP BY ts, dst_series, src_series
ORDER BY push DESC;

COMMIT;
