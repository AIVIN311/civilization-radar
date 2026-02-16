# Task — Live Status Receipt (v0.7 Date Bucket Contract)

Date: 2026-02-16  
Scope: collect live receipt artifacts and time-bucket semantics only

## Goal

- Add a non-invasive live receipt after collect completes.
- Provide deterministic evidence for runtime snapshot freshness without touching DB/promote/scoring.
- Lock date-bucket semantics for forward compatibility: `ts` (UTC date) first, `date` fallback.

## Allowed changes

- Add `ops/write_live_status.py`
- Update `ops/collect_snapshots_weekday.ps1` to invoke live receipt writer (non-blocking)
- Update `docs/ops/RUNBOOK.md` receipt expectations and date-bucket semantics
- Add this task log

## Do-not-touch list

- `persistence_v1.py` algorithms:
  - `compute_tag_persistence`
  - `classify_ers`
  - `compute_event_kernel`
- `metrics_v02.W` path assumptions
- Strength/push/gate paths
- DB schema
- Promote flow semantics
- Pipeline main flow semantics

## Verification steps

1. Run collect entry command:
   - `powershell -ExecutionPolicy Bypass -File .\ops\collect_snapshots_weekday.ps1`
2. Confirm live artifacts exist:
   - `Test-Path .\output\live\live_snapshot_status.json`
   - `Test-Path .\output\live\latest_day_domains.txt`
3. Validate receipt schema fields:
   - `Get-Content .\output\live\live_snapshot_status.json`
   - ensure `bad_json_lines`, `empty_lines`, `max_date`, `today_unique_domains`, `input_sha256`
4. Verify date-bucket fallback behavior on current data shape:
   - current rows are `date`-only and receipt still computes valid `max_date`
5. Non-blocking logic verification:
   - inspect `ops/collect_snapshots_weekday.ps1` branch where receipt failure emits warning only
6. Repo status check:
   - `git status --short`

## Results / notes

- Collect run succeeded:
  - command: `powershell -ExecutionPolicy Bypass -File .\ops\collect_snapshots_weekday.ps1`
  - exited `0`
  - collect summary showed `zones_scanned=55`, `rows_written=0`, `since=2026-02-15`
  - live receipt summary showed:
    - `max_date=2026-02-16`
    - `today_unique_domains=55`
    - `total_rows=363`
    - `bad_json_lines=0`
    - `empty_lines=0`
- Live artifacts verification passed:
  - `output/live/live_snapshot_status.json` exists
  - `output/live/latest_day_domains.txt` exists (`55` lines)
- Receipt schema verification passed:
  - `bad_json_lines` present
  - `empty_lines` present
  - `dups_date_domain_estimate` present and `null` by design
  - `input_sha256` present
- Date-bucket fallback verification passed on current `date`-only input shape:
  - valid `min_date=2026-02-10`, `max_date=2026-02-16`
- Non-blocking branch behavior verified with controlled failure simulation:
  - invoking a missing receipt script produced warning
  - warning branch completed and shell exited `0`

## Follow-ups

- Optional future enhancement: add explicit duplicate estimate metric when requirements are defined.
