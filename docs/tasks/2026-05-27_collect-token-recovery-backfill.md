# 2026-05-27 Collect Token Recovery Backfill

## Goal

Restore Cloudflare snapshot collection after the local live receipt showed `max_date=2026-05-18`.

## Allowed Changes

- Fix local environment shape needed by the collect script.
- Enable VS Code terminal `.env` injection for Python.
- Run deduped snapshot backfill through the existing collect script.
- Refresh live status receipt.

## Do-Not-Touch List

- Do not change scoring, gate, kernel, persistence, DB schema, or pipeline flow.
- Do not rotate or expose secrets in logs.
- Do not modify render behavior.

## Verification Steps

- Verify Cloudflare token is present and active without printing the token.
- Verify `/zones` API can read the expected account zones.
- Run a temporary-output smoke check before writing to `input/snapshots.jsonl`.
- Run deduped backfill with `cf_pull_daily_v2.py --days 10 --out input\snapshots.jsonl`.
- Refresh `output/live/live_snapshot_status.json` with `ops/write_live_status.py`.
- Check latest daily counts and JSON parse health.

## Results / Notes

- Token verification succeeded: status `active`.
- Zones API succeeded: `67` zones.
- Temporary smoke check succeeded: `67` zones scanned, `134` temp rows for UTC dates `2026-05-26` and `2026-05-27`.
- Formal backfill appended `603` rows, matching `9` missing dates times `67` domains.
- Live receipt after backfill:
  - `max_date`: `2026-05-27`
  - `today_unique_domains`: `67`
  - `total_rows`: `6995`
  - `bad_json_lines`: `0`
  - `empty_lines`: `0`
- Recent date buckets from `2026-05-13` through `2026-05-27` each show `67` rows.

## Follow-Ups

- Let the next scheduled `CivilizationRadar-WeekdaySnapshots` run prove scheduler-side environment continuity.
- Before sealing the May memo, re-check month integrity after natural month-end release.
