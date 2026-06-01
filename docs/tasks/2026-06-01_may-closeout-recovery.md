# 2026-06-01 May Closeout Recovery

## Goal

- Complete the 2026-05 snapshot window after the month-end receipt showed the input stalled at `2026-05-27`.
- Re-run the May month-end quality gate without changing scoring, gate, kernel, persistence, DB schema, or pipeline flow.
- Record whether the May memo can be treated as an observation memo versus a fully pushed release.

## Allowed Changes

- Deduped append of missing Cloudflare snapshot rows for `2026-05-28` through `2026-05-31`.
- Refresh `output/live/live_snapshot_status.json`.
- Run the existing month-end release path in a recovered `2026-05-31` context with tag push skipped.
- Documentation notes for this recovery and the 2026-05 observation memo.

## Do-Not-Touch List

- `persistence_v1.py`
- `compute_tag_persistence`
- `classify_ers`
- `compute_event_kernel`
- `metrics_v02.W` path assumptions
- strength / push / gate paths
- DB schema
- pipeline main flow
- render fallback behavior
- secrets or token rotation

## Verification Steps

- Confirm current gap in `input/snapshots.jsonl`.
- Verify `.env` contains `CF_API_TOKEN` without printing the token.
- Verify Cloudflare `/user/tokens/verify`.
- Verify Cloudflare `/zones` reads the expected account zones.
- Run `cf_pull_daily_v2.py` to a temporary output path first.
- Append only rows for `2026-05-28` through `2026-05-31` to `input/snapshots.jsonl`.
- Run `ops/write_live_status.py`.
- Re-run `ops/month_end_release.ps1` with a recovered `2026-05-31` time context and `-SkipTagPush`.
- Inspect the May month-end receipt and latest quality reports.

## Results / Notes

- Pre-recovery live receipt:
  - `max_date`: `2026-05-27`
  - `total_rows`: `6995`
  - `today_unique_domains`: `67`
  - `bad_json_lines`: `0`
- Scheduler boundary before manual recovery:
  - `CivilizationRadar-WeekdaySnapshots`: last run `2026-05-28 18:00:01`, last result `1`
  - `CivilizationRadar-FridayPromote`: last run `2026-05-29 18:00:00`, last result `0`
  - `CivilizationRadar-MonthEndPipelineTag`: last run `2026-05-31 19:00:01`, last result `1`
- Cloudflare verification:
  - token verify HTTP `200`
  - token status `active`
  - `/zones` HTTP `200`
  - zones total count `67`
- Temporary collector smoke:
  - command: `.venv\Scripts\python.exe -u cf_pull_daily_v2.py --days 5 --out output\tmp\may_closeout_backfill_20260601T062559Z.jsonl`
  - zones scanned: `67`
  - rows written to temp: `402`
  - temp rows included `67` rows each for `2026-05-27`, `2026-05-28`, `2026-05-29`, `2026-05-30`, `2026-05-31`, and `2026-06-01`
- Real append:
  - appended only `2026-05-28` through `2026-05-31`
  - appended rows: `268`
  - each appended date has `67` domains
  - `2026-06-01` rows were intentionally not appended
- Post-recovery live receipt:
  - `max_date`: `2026-05-31`
  - `total_rows`: `7263`
  - `today_unique_domains`: `67`
  - `bad_json_lines`: `0`
  - `empty_lines`: `0`
- Recovered May month-end gate:
  - receipt: `output/reports/month_end_20260531T110500Z.json`
  - status: `success_no_push`
  - `eval_ok`: `true`
  - `promoted_latest`: `true`
  - `critical_failed`: `[]`
  - `tag_name`: `radar-release-202605`
  - `tag_created`: `false`
  - `tag_pushed`: `false`
  - `tag_action`: `skipped_by_flag`
- `output/latest/reports/eval_quality.json` and `output/latest/reports/eval_quality_monthly.json` both show `ok: true`.
- `output/latest/radar.db` counts after recovered promote:
  - `snapshots_v01`: `7263`
  - `metrics_v02`: `7263`
  - `events_v01`: `8`
  - `chain_edges_v10`: `169`
  - `series_chain_v10`: `330`
- Link/file checks:
  - `docs/observations/2026-05-civilization-radar-monthly-observation-memo-v0.1.md`: exists
  - `docs/tasks/2026-06-01_may-closeout-recovery.md`: exists
  - `docs/README.md`: updated with the 2026-05 observation memo link
- Git status note:
  - The worktree was already dirty before this task (`.vscode/settings.json`, `docs/context/THREE_PROJECTS_OVERVIEW.md`, and several untracked docs/task files).
  - This task added `docs/tasks/2026-06-01_may-closeout-recovery.md`, added `docs/observations/2026-05-civilization-radar-monthly-observation-memo-v0.1.md`, and updated `docs/README.md`.
  - Snapshot/output recovery artifacts did not appear in `git status`, consistent with generated artifact handling.

## Follow-Ups

- The collector was manually recovered, but the scheduler is not yet re-proven. Let the next natural `CivilizationRadar-WeekdaySnapshots` run prove scheduler-side continuity.
- Push or create `radar-release-202605` only after explicit operator approval, because this recovery intentionally used `-SkipTagPush`.
- Treat `2026-05-14 03:18 Asia/Taipei` as a Cloudflare WAF intervention boundary when comparing pre/post May traffic.
