-- scripts/sql/views_v03_series_chain_latest.sql

BEGIN;

CREATE VIEW IF NOT EXISTS v03_series_chain_latest AS
WITH mx AS (SELECT MAX(ts) AS ts FROM v02_series_w_ts),

base AS (
  SELECT
    ts,
    series,
    W_avg
  FROM v02_series_w_ts
  WHERE ts = (SELECT ts FROM mx)
),

proj AS (
  -- W_proj：把「外來推力」加進去（最簡版）
  SELECT
    b.series AS series,
    b.W_avg AS W_avg,
    (b.W_avg + COALESCE(SUM(e.push), 0.0)) AS W_proj,
    COALESCE(MAX(CASE WHEN e.push>0 THEN e.src_series END), '') AS top_src,
    COALESCE(MAX(e.share), 0.0) AS share,
    COALESCE(MAX(e.push), 0.0) AS push,
    1 AS chain_flag
  FROM base b
  LEFT JOIN v03_chain_edges_latest e
    ON e.dst_series = b.series
   AND e.ts = b.ts
  GROUP BY b.series
),

final AS (
  SELECT
    (SELECT ts FROM mx) AS ts,
    series,
    W_avg,
    W_proj,
    CASE
      WHEN W_proj >= 2.30 THEN '事件'
      WHEN W_proj >= 1.80 THEN '警戒'
      WHEN W_proj >= 1.20 THEN '可疑'
      ELSE '背景'
    END AS status,
    chain_flag,
    top_src,
    share,
    push,
    0 AS domains,
    0 AS L3_domains
  FROM proj
)
SELECT * FROM final
ORDER BY W_proj DESC, W_avg DESC;

COMMIT;
