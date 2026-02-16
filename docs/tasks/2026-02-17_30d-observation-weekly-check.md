# Task — 30-Day Observation Weekly Check Flow

Date: 2026-02-17  
Window: 2026-02-16 to 2026-03-18 (Asia/Taipei)  
Scope: operations checks and reporting only

## Goal

- Run a fixed weekly inspection flow during the 30-day observation period.
- Detect scheduler/data/gate drift early without changing baseline behavior.
- Keep checks deterministic, repeatable, and fast to execute.

## Allowed changes

- Docs-only weekly checklist and command matrix.

## Do-not-touch list

- `src/persistence_v1.py` algorithms:
  - `compute_tag_persistence`
  - `classify_ers`
  - `compute_event_kernel`
- `metrics_v02.W` path assumptions
- strength / push / gate logic
- DB schema and pipeline flow

## Weekly fixed rhythm

### Mon-Thu (18:10-18:30)

Purpose: verify collect health after `CivilizationRadar-WeekdaySnapshots` (18:00).

Run:

```powershell
schtasks /Query /TN "CivilizationRadar-WeekdaySnapshots" /V /FO LIST
Get-Content .\output\live\live_snapshot_status.json
Get-Item .\input\snapshots.jsonl
git status --short
```

Pass:
- task `Last Result = 0`
- `live_snapshot_status.json` readable
- `max_date` is fresh (not older than 1 calendar day)
- `today_unique_domains > 0`
- `bad_json_lines = 0`
- no unexpected snapshot pollution in `git status`

Escalate if fail:
1. Re-run collect:
   - `powershell -ExecutionPolicy Bypass -File .\ops\collect_snapshots_weekday.ps1`
2. Re-check task + receipt.
3. If still failing, stop feature changes and triage root cause first.

### Friday (18:10-19:00)

Purpose: verify promote/acceptance health after `CivilizationRadar-FridayPromote` (18:00).

Run:

```powershell
schtasks /Query /TN "CivilizationRadar-FridayPromote" /V /FO LIST
Get-ChildItem .\output\reports\acceptance_latest_*.json | Sort-Object LastWriteTimeUtc -Descending | Select-Object -First 1
Get-Content .\output\latest\reports\eval_quality.json
Get-Item .\output\latest\radar.db
```

Pass:
- task `Last Result = 0`
- newest `acceptance_latest_*.json` exists and is fresh (Friday run window)
- `output/latest/reports/eval_quality.json` has `ok = true`
- `output/latest/radar.db` refreshed in current run window

Escalate if fail:
1. Re-run promote:
   - `powershell -ExecutionPolicy Bypass -File .\ops\promote_latest.ps1`
2. If still failing, inspect the first failing gate and stop non-ops work until resolved.

### Daily month-end guard (19:05 on any day)

Purpose: confirm month-end task remains healthy and non-disruptive.

Run:

```powershell
schtasks /Query /TN "CivilizationRadar-MonthEndPipelineTag" /V /FO LIST
```

Pass:
- task `Last Result = 0`
- non-month-end days should be no-op success

## Weekly checkpoint dates (fixed)

- Week 1 checkpoint: Friday, 2026-02-20
- Week 2 checkpoint: Friday, 2026-02-27
- Week 3 checkpoint: Friday, 2026-03-06
- Week 4 checkpoint: Friday, 2026-03-13
- Final 30-day closeout: Wednesday, 2026-03-18

## Weekly report template (append per checkpoint)

Record each Friday:
- Date/time (Asia/Taipei)
- Weekday collect task status
- Friday promote task status
- Month-end task status
- `max_date`
- `today_unique_domains`
- latest acceptance report filename + timestamp
- `eval_quality.ok`
- incidents/actions/follow-up owners

## Verification steps

1. Confirm all referenced commands/paths exist:
   - `ops/collect_snapshots_weekday.ps1`
   - `ops/promote_latest.ps1`
   - `ops/month_end_release.ps1`
   - `output/live/live_snapshot_status.json` (runtime)
   - `output/latest/reports/eval_quality.json` (runtime)
2. Confirm this checklist matches current acceptance contract:
   - `scripts/run_acceptance_latest.py` default v0.7 path
3. Confirm docs-only scope:
   - `git status --short`

## Results / notes

- Checklist created for 30-day observation execution.
- No runtime behavior changed.

## Follow-ups

- Optional: add `ops/weekly_observation_check.ps1` to auto-generate a weekly JSON report under `output/reports/` using this checklist.
