# 2026-05 Civilization Radar Monthly Observation Memo v0.1

Date: 2026-06-01
Month: 2026-05
Status: recovered local month-end gate passed; tag push skipped
Role: interpretation memo only; not a scoring, gate, kernel, or pipeline change

## 0. Memo Position

2026-05 is the first month after the April observation baseline where the signal did not merely continue. It expanded sharply.

This memo does not claim source, intent, AI ingestion, or downstream use. It records that May has a complete recovered snapshot window, a much larger request surface than April, a clear late-month plateau, and a mid-month Cloudflare WAF intervention boundary that must stay visible in later comparisons.

## 1. Month Integrity

- Days complete: 31/31 after recovery
- Domains daily: 67/67
- Rows: 2077
- `bad_json_lines`: 0
- Input max date: 2026-05-31
- Month-end release: recovered local gate success
- Release receipt: `output/reports/month_end_20260531T110500Z.json`
- Release tag: `radar-release-202605`
- `eval_ok`: true
- `promoted_latest`: true
- `tag_pushed`: false, intentionally skipped during recovery

Operational note:

- The natural 2026-05-31 month-end run failed before recovery with `events_empty`.
- The recovered run appended only missing May rows, re-ran the existing month-end path, passed the quality gate, and promoted `output/latest`.
- This memo should be read as a local recovered monthly observation. It is not proof that the remote release tag was pushed.

## 2. Cloudflare Account-Level Snapshot

No account-level 30d bandwidth / visits / pageviews artifact was captured in the repo during this memo.

Repo-owned per-zone snapshot totals for 2026-05:

- Requests / `dns_total`: 57.10M
- Cached / `cf_served`: 12.20M
- Origin / `origin_served`: 44.90M
- Edge-origin ratio: 0.272

For comparison, the repo-owned April per-zone request total was 9.40M. May is roughly 6.1x April by the same snapshot surface.

## 3. Country Concentration

Country concentration is not available from the repo-owned May snapshot artifact.

Do not infer geography from this memo. A future account-level Cloudflare export or artifact provider is needed before country concentration can be compared to April.

## 4. Interpretation Status

- 不判定來源。
- 不宣稱 AI ingestion。
- 不把 country、institution、actor 或 bot identity 當成已知事實。
- 只記錄：請求面明顯放大、late-month plateau、series distribution shift、以及 2026-05-14 WAF intervention boundary。

## 5. Next Checks

- Top paths by domain
- Top ASNs / user agents
- Search and AI crawler split after WAF boundary
- Cache behavior for high `cf_served` domains
- Whether late-May plateau repeats in early June
- Natural scheduler continuity after manual recovery
- Whether to push or separately seal `radar-release-202605`

## 6. Month Shape

May is not a single spike. It has a step-up shape:

- W1 05/01-05/07: 5,559,726
- W2 05/08-05/14: 9,527,933
- W3 05/15-05/21: 16,680,452
- W4 05/22-05/28: 17,497,689
- W5 05/29-05/31: 7,831,419

Primary peak cluster:

- 2026-05-31: 3,307,633
- 2026-05-30: 3,292,821
- 2026-05-24: 3,287,518

Secondary high plateau:

- 2026-05-25: 2,880,201
- 2026-05-17: 2,865,305
- 2026-05-16: 2,762,354
- 2026-05-26: 2,733,305
- 2026-05-19: 2,718,433

Cloudflare WAF boundary:

- 2026-05-14 03:18 Asia/Taipei is an observation-environment intervention point.
- Pre-WAF 05/01-05/13 average: 1.09M requests/day
- Boundary day 05/14: 0.97M requests
- Post-WAF 05/15-05/31 average: 2.47M requests/day

Conservative reading:

- The post-boundary increase is real in the collected artifact.
- The WAF change means scanner-path and generic-client suppression may also be changing what remains visible.
- Do not treat the post-05/14 surface as a clean organic demand comparison against early May.

## 7. Series Distribution

The 2026-05 series distribution is:

- `algorithmic_governance`: 11,999,154
- `synthetic_systems`: 11,622,192
- `civilization_resilience`: 8,770,584
- `identity_data`: 8,062,468
- `monetary_infrastructure`: 7,156,342
- `offworld_expansion`: 6,517,102
- `human_manifesto`: 2,969,377

Conservative reading:

- The April top pair, `synthetic_systems` and `algorithmic_governance`, remains central.
- May adds broader lift in `civilization_resilience`, `identity_data`, and `monetary_infrastructure`.
- The shape is less like one isolated theme and more like several high-structure series being read together.

## 8. Domain Watchlist

High-contact nodes:

- `biometricliability.com`: 2,179,210
- `energyjurisdiction.com`: 2,084,012
- `thepowerofdefault.com`: 2,083,787
- `syntheticliability.com`: 1,867,011
- `sovereignairesilience.com`: 1,803,037
- `climateinterventionism.com`: 1,748,009
- `unannouncedsovereignty.com`: 1,714,419
- `thefirstmarscitizen.com`: 1,647,820
- `theincrementalism.com`: 1,635,400
- `thepacificpivot.com`: 1,623,563

Continuation from April watchlist:

- `energyjurisdiction.com` moved from April rank 8 to a May top-three node.
- `syntheticliability.com` stayed high and strengthened.
- `thepacificpivot.com` stayed in the high-contact group.
- `climateinterventionism.com` rose into the top-ten group.

Cache-heavy watch:

- `siliconmetabolism.com` has `cf_served` above origin served for the month.
- `syntheticrealitycrisis.com` remains cache-heavy relative to request rank.
- Review cache behavior separately from semantic interpretation.

## 9. Governance Note

This memo is based on recovered local artifacts. The recovery did not change scoring, gates, kernel, persistence, DB schema, or pipeline flow.

The May closeout was recovered with `-SkipTagPush`; therefore the memo can support interpretation, but it should not be cited as a remote tag-pushed release unless `radar-release-202605` is later created and pushed.

## 10. Short Reading

- 5 月不是 4 月的延續而已，是量級放大：repo-owned request total 從 4 月 9.40M 上升到 5 月 57.10M。
- 月內形狀是階梯式抬升，5/15 後進入高位平台，5/30-5/31 接近並超過 5/24 主峰。
- 主軸仍是 `algorithmic_governance` 與 `synthetic_systems`，但 `civilization_resilience`、`identity_data`、`monetary_infrastructure` 也一起抬升。
- 4 月 watchlist 裡的 `energyjurisdiction.com`、`syntheticliability.com`、`thepacificpivot.com`、`climateinterventionism.com` 在 5 月都有延續價值。
- 5/14 WAF intervention 是解讀邊界：後段數字更高，但可見流量組成已經被政策改變過。
- 目前可以把 5 月當作 recovered local observation memo；不要把它說成遠端 release tag 已經封箱。

## 11. Boundary

Allowed claims:

- 2026-05 collected artifacts are complete after recovery.
- May request volume is much larger than April on the same repo-owned snapshot surface.
- Late May forms a high plateau, not a one-day-only anomaly.
- `algorithmic_governance` and `synthetic_systems` remain the top series, with broader lift across resilience, identity, monetary, and offworld series.
- `2026-05-14 03:18 Asia/Taipei` must be preserved as a WAF intervention boundary.

Do not claim from this memo alone:

- AI systems are using these domains.
- A country, institution, or actor is responsible.
- A concept has market validation.
- Commercial value is proven.
- `radar-release-202605` was pushed remotely.
