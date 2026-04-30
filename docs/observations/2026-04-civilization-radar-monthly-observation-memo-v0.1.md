# 2026-04 Civilization Radar Monthly Observation Memo v0.1

Date: 2026-04-30
Month: 2026-04
Status: first natural month-end observation memo
Role: interpretation memo only; not a scoring, gate, kernel, or pipeline change

## 0. Memo Position

2026-04 is the first month where Civilization Radar moves from traffic surprise into signal shape.

This memo does not claim source, intent, or downstream use. It records that the month has structure: a complete natural-month window, a successful month-end release, a visible time waveform, a series distribution, a domain watchlist, and one small mapping governance fix.

## 1. Month Integrity

- Days complete: 30/30
- Domains daily: 67/67
- Rows: 2010
- `bad_json_lines`: 0
- Input max date: 2026-04-30
- Month-end release: success
- Release receipt: `output/reports/month_end_20260430T110003Z.json`
- Release tag: `radar-release-202604`
- `eval_ok`: true
- `tag_pushed`: true

## 2. Cloudflare Account-Level Snapshot

Source: operator-provided account-level 30d snapshot for the 2026-04 memo.

- 30d requests: 26.24M
- Bandwidth: 104.05GB
- Visits: 23.42M
- Pageviews: 24.21M

## 3. Country Concentration

- Russia: 20.33M
- UK: 2.45M
- Canada: 1.09M
- US: 731k
- France: 671k

## 4. Interpretation Status

- 不判定來源。
- 不宣稱 AI ingestion。
- 只記錄：高度集中、自動化可能性高、讀取頻率上升。
- This memo treats the account-level pattern as an observation surface, not attribution proof.

## 5. Next Checks

- Top domains
- Top paths
- Top ASNs / user agents
- Series-level distribution
- Spike days

## 6. Month Shape

4 月不是平平的一個月。它有明確節奏：前段建立基底，中段爆發，後段維持高位。

- W1 04/01-04/07: 1,388,495
- W2 04/08-04/14: 1,666,272
- W3 04/15-04/21: 3,021,471
- W4 04/22-04/28: 2,649,793
- W5 04/29-04/30: 670,075

Primary peak:

- 2026-04-19: 1,038,065
- Label: April primary peak day

Secondary wave:

- 2026-04-25: 663,110
- 2026-04-26: 565,006

Month-end signal:

- 2026-04-30: 386,621

## 7. Series Distribution

After filling the April domain mapping gap, the 2026-04 series distribution is:

- `synthetic_systems`: 2,180,432
- `algorithmic_governance`: 1,850,488
- `monetary_infrastructure`: 1,408,084
- `identity_data`: 1,351,519
- `civilization_resilience`: 1,274,695
- `offworld_expansion`: 784,560
- `human_manifesto`: 546,328

Conservative reading:

- 4 月被讀取最強的，不是詩意型或品牌型節點，而是制度、合成、治理、基建、身份這些高結構張力節點。
- This is not evidence of intent. It is a distribution pattern worth preserving and comparing against 2026-05.

## 8. Domain Watchlist

High-contact nodes:

- `thepowerofdefault.com`
- `biometricliability.com`
- `volatilityasinfrastructure.com`

Emerging watchlist for 2026-05:

- `thepacificpivot.com`
- `energyjurisdiction.com`
- `syntheticliability.com`
- `algorithmicallocation.com`
- `climateinterventionism.com`

Reason to watch:

- These nodes connect geography, resource jurisdiction, synthetic liability, allocation, and intervention semantics.
- If they continue rising in 2026-05, they should be reviewed as recurring rather than one-month spikes.

## 9. Governance Note

Before this memo, 13 April domains were present in snapshots but absent from `config/domains_50.fixed.json` / `config/series_map.json`, leaving roughly 438,651 April DNS rows outside clean series-level analysis.

Those mappings were filled before sealing this memo. This is a metadata classification fix only; it does not change scoring, gate, kernel, persistence, DB schema, scheduler, or the April month-end receipt.

## 10. Short Reading

- 4 月資料完整收齊，且自然月結成功，這是第一個可用的完整自然月觀測樣本。
- 主要 activity 在月中後段放大：4/19 是主峰，4/25-4/26 是第二波，4/30 月結日仍有事件訊號。
- Series 層級主軸是 `synthetic_systems` 與 `algorithmic_governance`；`monetary_infrastructure`、`identity_data`、`civilization_resilience` 是第二層共同抬升。
- Account-level country concentration 明顯偏向少數國家，但目前只記錄集中度，不推論操作者或意圖。
- 下月重點不是追單一尖峰，而是比對 5 月是否延續 4 月中下旬的高位節奏。

## 11. Boundary

Use this memo as observation, not declaration.

Allowed claims:

- 4 月中下旬有明顯抬升。
- `synthetic_systems` / `algorithmic_governance` 是主軸。
- 少數 domain 成為高接觸節點。
- 4/19 is the April primary peak day.
- 4/25-4/26 is the April secondary wave.
- 2026-05 should verify continuation or reversion.

Do not claim from this memo alone:

- AI systems are using these domains.
- A country, institution, or actor is responsible.
- A concept has market validation.
- Commercial value is proven.
