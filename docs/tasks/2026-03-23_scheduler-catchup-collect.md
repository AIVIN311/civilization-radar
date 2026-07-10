Goal
- Recover missed weekday snapshot collection on 2026-03-23 after the laptop was closed during the scheduled run window.

Allowed changes
- Run the canonical collect command from [RUNBOOK](C:/dev/civilization-radar/docs/ops/RUNBOOK.md).
- Record operational verification notes for this manual catch-up run.
- No scoring, gate, kernel, schema, or pipeline flow changes.

Do-not-touch list
- `persistence_v1.py` algorithms and classification logic
- scoring / gate / kernel logic
- DB schema
- pipeline main flow

Verification steps
- Check pre-run scheduler status for `CivilizationRadar-WeekdaySnapshots`
- Run `powershell -ExecutionPolicy Bypass -File .\ops\collect_snapshots_weekday.ps1`
- Run `powershell -ExecutionPolicy Bypass -File .\ops\promote_latest.ps1`
- Read `output/live/live_snapshot_status.json`
- Inspect tail of `input/snapshots.jsonl`
- Read `output/reports/acceptance_latest_*.json`
- Read `output/latest/reports/eval_quality.json`
- Inspect `output/latest/radar.db` timestamp ranges
- Confirm `git status --short` did not gain new tracked-source pollution

Results / notes
- Manual collect run completed successfully on 2026-03-23 20:45 +08:00.
- Collect command reported `daysBack=3`, `zones_scanned=67`, `rows_written=204`, and exit code `0`.
- Live receipt now reports `max_date = 2026-03-23`, `today_unique_domains = 67`, `total_rows = 2640`.
- Tail inspection of `input/snapshots.jsonl` shows rows for `2026-03-23`.
- `git status --short` after the run remained limited to pre-existing unrelated changes:
- `M docs/context/THREE_PROJECTS_OVERVIEW.md`
- `?? .codex/`
- `?? docs/context/RESEARCH_PRODUCT_LAYER_MAP.md`
- Scheduled task check indicates:
- `CivilizationRadar-WeekdaySnapshots` is the weekday collect task and is scheduled for `18:00`.
- `CivilizationRadar-MonthEndPipelineTag` is a separate `19:00` task and is not the weekday snapshot collector.
- `CivilizationRadar-MonthEndPipelineTag` showed `Last Run Time = 2026-03-23 20:45:57`, `Last Result = -2147020576` (`0x800710e0`: "The operator or administrator has refused the request").
- Promote path also completed successfully on 2026-03-23 20:48 +08:00 via `powershell -ExecutionPolicy Bypass -File .\ops\promote_latest.ps1`.
- Fresh acceptance receipt written at `output/reports/acceptance_latest_20260323T124756Z.json`.
- Promoted latest receipt at `output/latest/reports/eval_quality.json` reports `ok = true`.
- `output/latest/radar.db` and `output/latest/dashboard_v04.html` refreshed at approximately 2026-03-23 20:47:58 to 20:47:59 +08:00.
- Important scope note: this promote flow refreshed `output/latest` from accepted v0.7 artifacts sourced from `output/acceptance_v07/run_tw_a/latest`, and the acceptance run itself used `input/snapshots.geo.sample.jsonl`.
- Therefore, `output/latest` is now fresh as a weekly accepted artifact, but it is not a live rendering of the newly collected `input/snapshots.jsonl` rows from 2026-03-23.
- Post-promote inspection of `output/latest/radar.db` shows sample acceptance ranges:
- `snapshots_v01.ts`: `2026-02-03T00:00:00+08:00` to `2026-02-07T00:00:00+08:00`
- `events_v01.date`: `2026-02-07` to `2026-02-07`
- This matches the documented baseline cadence that promotion to `output/latest` happens on accepted weekly artifacts and can lag live collection state within the week.

Follow-ups
- If the goal is to render/dashboard today's live collected data rather than refresh the accepted weekly artifact, run the full pipeline explicitly against `input/snapshots.jsonl` with manual approval.
