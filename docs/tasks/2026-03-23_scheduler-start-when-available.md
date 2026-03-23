Goal
- Harden baseline scheduler registration so missed runs can catch up after the host becomes available again.

Allowed changes
- `ops/register_weekly_tasks.ps1`
- `docs/ops/weekly_rhythm.md`
- this task log

Do-not-touch list
- `ops/collect_snapshots_weekday.ps1`
- `ops/promote_latest.ps1`
- `ops/month_end_release.ps1`
- scoring / gate / kernel / persistence logic
- DB schema
- pipeline flow
- unrelated local files:
- `docs/context/THREE_PROJECTS_OVERVIEW.md`
- `docs/context/RESEARCH_PRODUCT_LAYER_MAP.md`
- `.codex/`

Verification steps
- Capture current scheduler XML and settings for `CivilizationRadar-WeekdaySnapshots`
- Confirm current task settings show `StartWhenAvailable = False`
- Patch registrar to enable `StartWhenAvailable` during same-user non-interactive registration
- Parse `ops/register_weekly_tasks.ps1` for syntax errors
- Update canonical ops note to describe catch-up behavior and `WakeToRun` deferral
- Check `git status --short`

Results / notes
- Pre-change scheduler state for all three baseline tasks showed:
- `StartWhenAvailable = False`
- `WakeToRun = False`
- `DisallowStartIfOnBatteries = True`
- `StopIfGoingOnBatteries = True`
- `CivilizationRadar-WeekdaySnapshots` emitted Task Scheduler `Event ID 153` on 2026-03-23 20:45:57 +08:00: missed schedule, not launched, consider `start the task when available`.
- `ops/register_weekly_tasks.ps1` now:
- keeps the existing `schtasks`-based registration flow
- exports each task XML after creation
- injects `<StartWhenAvailable>true</StartWhenAvailable>`
- re-imports the task XML using the same current-user password that was already provided for registration
- keeps `WakeToRun` out of scope for this slice
- keeps battery policy unchanged in this slice
- `docs/ops/weekly_rhythm.md` now documents the intended missed-schedule catch-up behavior and the still-disabled `WakeToRun` policy.
- Live scheduler mutation could not be completed non-interactively in this session because the current tasks use `LogonType = Password`, and both `Set-ScheduledTask` and COM re-registration required the Windows password again.
- Attempted direct mutation paths failed cleanly with `0x8007052E` (`The user name or password is incorrect`) because this session cannot answer the password prompt.
- Operator follow-through then completed successfully on 2026-03-23 around 20:58 +08:00 by running:
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\ops\register_weekly_tasks.ps1`
- Interactive password entry succeeded and all three baseline tasks were recreated plus re-imported with `StartWhenAvailable = true`.
- Post-registration XML verification confirmed `StartWhenAvailable = true` for:
- `CivilizationRadar-WeekdaySnapshots`
- `CivilizationRadar-FridayPromote`
- `CivilizationRadar-MonthEndPipelineTag`
- Post-registration verification also confirmed the registration preserved:
- `LogonType = Password`
- unchanged task names
- unchanged trigger cadence
- unchanged script paths
- `WakeToRun` still disabled by omission from task XML
- Repo-side fix and live host registration are now aligned.

Follow-ups
- Future scheduler misses should now catch up after the host becomes available again, without changing the current no-`WakeToRun` policy.
