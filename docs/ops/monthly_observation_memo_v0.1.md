# Monthly Observation Memo v0.1

Purpose: convert monthly surprise into comparable history.

Scope:
- One memo per natural month after month-end release succeeds.
- Interpretation-only. This memo does not change scoring, gates, kernel, scheduler, or baseline comparability.
- Account-level Cloudflare numbers may be operator-provided until an artifact provider exists.

File name:
- `docs/observations/YYYY-MM-civilization-radar-monthly-observation-memo-v0.1.md`

Required sections:

1. Month Integrity
   - days complete
   - domains per day
   - row count
   - `bad_json_lines`
   - month-end release status

2. Cloudflare Account-Level Snapshot
   - 30d requests
   - bandwidth
   - visits
   - pageviews

3. Country Concentration
   - top countries by request volume

4. Interpretation Status
   - no source attribution
   - no claim of AI ingestion
   - record only concentration, automation likelihood, and reading frequency trend

5. Next Checks
   - top domains
   - top paths
   - top ASNs / user agents
   - series-level distribution
   - spike days

6. Short Reading
   - 3-7 bullets max
   - Keep claims conservative and tied to observed artifacts.
