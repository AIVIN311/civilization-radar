# Task — Scheduler Recovery (Daily/Weekly/Monthly)

Date: 2026-02-13  
Scope: Windows Task Scheduler registration and smoke verification

## Goal

Restore automatic scheduler operations for:
- Weekday snapshot collection
- Friday promote latest
- Daily month-end self-gated release task

## Allowed changes

- Scheduler registration and verification
- Ops script bug fix required for scheduler execution
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

1. Register scheduler tasks:
   - `powershell -NoProfile -ExecutionPolicy Bypass -File .\ops\register_weekly_tasks.ps1`
2. Query task definitions:
   - `schtasks /Query /TN "CivilizationRadar-WeekdaySnapshots" /V /FO LIST`
   - `schtasks /Query /TN "CivilizationRadar-FridayPromote" /V /FO LIST`
   - `schtasks /Query /TN "CivilizationRadar-MonthEndPipelineTag" /V /FO LIST`
3. Timezone check:
   - `tzutil /g`
4. Manual smoke run:
   - `schtasks /Run /TN "CivilizationRadar-WeekdaySnapshots"`
   - `schtasks /Run /TN "CivilizationRadar-FridayPromote"`
   - `schtasks /Run /TN "CivilizationRadar-MonthEndPipelineTag"`
5. Health checks:
   - All 3 tasks return `Last Result = 0`
   - `output/latest/reports/eval_quality.json` exists and `ok = true`
   - runtime artifacts refresh as expected
6. Repo status check:
   - `git status --short`

## Results / notes

- Registration succeeded for all three tasks.
- Task definitions matched expected schedule and command mapping:
  - `CivilizationRadar-WeekdaySnapshots`: Weekly Mon-Thu 18:00
  - `CivilizationRadar-FridayPromote`: Weekly Fri 18:00
  - `CivilizationRadar-MonthEndPipelineTag`: Daily 19:00 (self-gated in script)
- Logon mode is `Interactive only` for all three tasks.
- Host timezone returned `Taipei Standard Time`.
- Initial smoke run showed `Last Result = 1` on Friday/month-end tasks.
- Root cause: invalid month-end date construction in two scripts (`Get-Date $d.Year $d.Month 1`).
- Fixed with named parameters:
  - `Get-Date -Year $d.Year -Month $d.Month -Day 1`
- Re-ran smoke; all three tasks completed with `Last Result = 0`.
- `eval_quality.json` remained present and parsed with `ok = true`.

## Follow-ups

- Optional cleanup (not part of this recovery scope):
  - Remove unreachable tail commands after `exit 0` in `ops/promote_latest.ps1`
  - Remove trailing stray text at end of `ops/month_end_release.ps1`
