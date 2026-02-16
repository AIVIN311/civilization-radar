# Task — Collect Retry Hardening (5xx + Timeout/Connection)

Date: 2026-02-16  
Scope: Weekday snapshot collection reliability and observability only

## Goal

- Harden collect flow against transient upstream failures so a single 5xx does not fail the full run.
- Keep scheduler/operator visibility high with progress and retry logs.
- Preserve baseline invariants and output contracts.

Root cause:
Upstream Cloudflare GraphQL transient 502 caused single-run failure; immediate rerun succeeded.

## Allowed changes

- `cf_pull_daily_v2.py` HTTP request retry/backoff behavior
- collect runtime progress/retry/done logging
- `ops/collect_snapshots_weekday.ps1` unbuffered python invocation
- Ops runbook diagnostics note
- Task log documentation

## Do-not-touch list

- `persistence_v1.py` algorithms:
  - `compute_tag_persistence`
  - `classify_ers`
  - `compute_event_kernel`
- `metrics_v02.W` path assumptions
- strength / push / gate paths
- DB schema
- pipeline main flow semantics

## Verification steps

1. Supplement current-day collect slot:
   - `powershell -ExecutionPolicy Bypass -File .\ops\collect_snapshots_weekday.ps1`
2. Confirm current-day records exist:
   - `Get-Content input/snapshots.jsonl -Tail 30 | Select-String "2026-02-16"`
   - `Get-Item input/snapshots.jsonl`
3. Enable Task Scheduler operational log:
   - `wevtutil set-log Microsoft-Windows-TaskScheduler/Operational /enabled:true`
   - `Get-WinEvent -ListLog 'Microsoft-Windows-TaskScheduler/Operational'`
4. Trigger scheduler task and inspect status:
   - `schtasks /Run /TN "CivilizationRadar-WeekdaySnapshots"`
   - `schtasks /Query /TN "CivilizationRadar-WeekdaySnapshots" /V /FO LIST`
5. Verify retry/progress/done logs on temp output:
   - `.\\.venv\\Scripts\\python.exe cf_pull_daily_v2.py --days 3 --out output/tmp/snapshots_probe_retry.jsonl`
6. Verify non-retry boundaries:
   - `CF_API_TOKEN=invalid_token_for_test` then run collect command once
   - call `request_with_retry(..., url="https://httpbin.org/status/429", ...)`
   - call `graphql(...)` with an invalid GraphQL field query
7. Repo status:
   - `git status --short`
8. Promote smoke verification:
   - `powershell -ExecutionPolicy Bypass -File .\ops\promote_latest.ps1`
   - confirm `output/latest/reports/eval_quality.json` has `ok = true`
   - confirm a fresh `output/reports/acceptance_latest_*.json` exists

## Results / notes

- Current-day records for `2026-02-16` were present in `input/snapshots.jsonl`.
- Manual collect succeeded (`LastExitCode=0`) and preserved data contract.
- Collect now prints deterministic runtime visibility lines:
  - `START ...`
  - `progress scanned=...`
  - `DONE zones_scanned=... rows_written=... elapsed=...`
- Temp-output collect verification passed:
  - `zones_scanned=55`
  - progress lines emitted every 10 zones and final zone
  - command exited `0`
- Non-retry boundary verification passed:
  - Invalid token produced immediate HTTP 400 failure
  - No retry loop was entered for non-retryable 4xx
  - HTTP 429 test exited on first attempt (`attempt=1/5`), no retry loop entered
  - GraphQL HTTP 200 + `errors` payload exited immediately with `GraphQL query failed...`
- Scheduler manual trigger verification passed:
  - `CivilizationRadar-WeekdaySnapshots` transitioned `Running -> Ready`
  - `Last Result` became `0`
- Promote smoke verification passed:
  - `ops/promote_latest.ps1` completed with gates passed
  - `output/latest/reports/eval_quality.json` reported `ok: true`
  - fresh report generated: `acceptance_latest_20260216T143900Z.json`
- Operational log auto-enable was blocked on this host/session:
  - `Failed to save configuration or activate log ... Access is denied.`
  - `IsEnabled` remains `False` (requires elevated shell).

## Follow-ups

- Re-run operational log enable command from an elevated PowerShell session.
- After enabling, validate event emission with one scheduler-triggered collect run.
