# Task - Manual Catch-up Collect

Date: 2026-05-11

## Goal
- Recover missed snapshot collection after the scheduled 18:00 run failed while the machine had no network connection.

## Allowed changes
- Run the canonical weekday collect command.
- Run a targeted deduped Cloudflare pull to fill the missing 2026-05-07 date bucket.
- Refresh live status receipt artifacts.

## Do-not-touch list
- Scoring, gate, kernel, and persistence logic
- DB schema
- Pipeline main flow
- Baseline comparability settings

## Verification steps
- Run `powershell -ExecutionPolicy Bypass -File .\ops\collect_snapshots_weekday.ps1`.
- Run `.venv\Scripts\python.exe -u cf_pull_daily_v2.py --days 5 --out input\snapshots.jsonl`.
- Run `.venv\Scripts\python.exe -u .\ops\write_live_status.py`.
- Group recent `input/snapshots.jsonl` rows by date.
- Read `output/live/live_snapshot_status.json`.
- Check `git status --short` for unexpected tracked-source pollution.

## Results / notes
- The canonical weekday collect completed successfully with `daysBack=3`, `zones_scanned=67`, and `rows_written=268`.
- The targeted deduped pull completed successfully with `days=5`, `zones_scanned=67`, and `rows_written=67`.
- Recent date buckets now show 67 rows each for 2026-05-07 through 2026-05-11.
- Live receipt reports `max_date = 2026-05-11`, `today_unique_domains = 67`, `total_rows = 5923`, `bad_json_lines = 0`, and `empty_lines = 0`.
- No scoring, gate, kernel, schema, or pipeline flow code was changed.

## Follow-ups
- If dashboard/latest artifacts should reflect the live collected rows immediately, run the full pipeline explicitly against `input/snapshots.jsonl`.
