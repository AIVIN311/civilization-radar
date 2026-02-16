# Weekly Rhythm

Monday
- Snapshot collection (automatic)

Friday
- Promote latest acceptance to output/latest

End of Month
- Full pipeline run
- Release tag
- Archive outputs
# Weekly Rhythm Automation v1.1 (Promotion-First)

## Rhythm
- Mon–Thu 18:00: collect snapshots only
- Fri 18:00: promote latest only (acceptance refresh)
- Daily 19:00: month-end job (self-gated; runs only on month-end)

## Collision Rule
- If month-end is Friday: Friday promote skips; month-end job runs the only heavy pipeline.

## Command Matrix
- collect: ops/collect_snapshots_weekday.ps1
- promote: ops/promote_latest.ps1
- acceptance target (via promote): scripts/run_acceptance_latest.py default v0.7 fast mode
- month-end: ops/month_end_release.ps1
- registrar: ops/register_weekly_tasks.ps1

## Trigger Matrix
| Task | When | Does |
|---|---|---|
| CivilizationRadar-WeekdaySnapshots | Mon–Thu 18:00 | Append snapshots (daysBack: Mon=3, else=1) |
| CivilizationRadar-FridayPromote | Fri 18:00 | run_acceptance_latest.py (default v0.7 fast mode) + gates |
| CivilizationRadar-MonthEndPipelineTag | Daily 19:00 | If month-end: full pipeline + eval_quality_monthly + tag push |

## Timezone Requirement
- Windows Task Scheduler uses host local timezone.
- Host Windows timezone MUST be Asia/Taipei.

## Failure Handling / Rerun Policy
- Weekday collect fails: re-run ops/collect_snapshots_weekday.ps1 manually.
- Promote fails: fix root cause then re-run ops/promote_latest.ps1 manually (no full pipeline).
- Month-end fails: fix root cause then re-run ops/month_end_release.ps1; idempotent tag behavior prevents duplicate tag errors.

## Known Windows Scheduler Pitfalls
- Host timezone controls trigger time (no per-task timezone).
- Run-as context affects env/.env/OneDrive access; start with interactive current user.
- OneDrive sync/lock can cause PermissionError; prefer stable local availability.
