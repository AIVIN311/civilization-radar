# 2026-06-26 June Snapshot Recovery

## Goal

Restore June 2026 Cloudflare snapshot coverage after inspection showed missing local rows for `2026-06-09` through `2026-06-11`.

## Allowed Changes

- Run temporary-output Cloudflare collector smoke checks.
- Run deduped backfill through `cf_pull_daily_v2.py`.
- Append missing runtime rows to `input/snapshots.jsonl`.
- Refresh `output/live/live_snapshot_status.json`.
- Manually trigger `CivilizationRadar-WeekdaySnapshots` once to prove scheduler-side execution.
- Record this recovery note.

## Do-Not-Touch List

- Do not change scoring, gate, kernel, persistence, DB schema, or pipeline flow.
- Do not rotate or expose secrets.
- Do not modify render behavior.

## Verification Steps

- Check June coverage in `input/snapshots.jsonl`.
- Verify `.env` shape without printing token values.
- Verify Cloudflare `/user/tokens/verify`.
- Verify Cloudflare `/zones` reads expected zones.
- Run a temporary-output smoke check covering the gap.
- Run the real deduped backfill.
- Refresh live status receipt.
- Re-check June coverage, duplicate `(date, domain)` keys, scheduler status, and git status.

## Results / Notes

- Pre-recovery live receipt:
  - `max_date`: `2026-06-25`
  - `today_unique_domains`: `67`
  - `total_rows`: `8737`
  - `bad_json_lines`: `0`
  - `empty_lines`: `0`
- Pre-recovery June gap:
  - `2026-06-09`: `0` rows
  - `2026-06-10`: `0` rows
  - `2026-06-11`: `0` rows
- Cloudflare verification:
  - token verify HTTP `200`
  - token status `active`
  - `/zones` HTTP `200`
  - zones total count `67`
- Temporary collector smoke:
  - command: `.venv\Scripts\python.exe -u cf_pull_daily_v2.py --days 18 --out output\tmp\june_gap_smoke_20260626T113613Z.jsonl`
  - `since`: `2026-06-08`
  - zones scanned: `67`
  - temp rows written: `1273`
  - temp coverage showed `67` rows and `67` unique domains for each date from `2026-06-08` through `2026-06-12`
- Real deduped backfill:
  - command: `.venv\Scripts\python.exe -u cf_pull_daily_v2.py --days 18 --out input\snapshots.jsonl`
  - `since`: `2026-06-08`
  - rows appended: `268`
  - expected interpretation: `201` rows for missing `2026-06-09` through `2026-06-11`, plus `67` rows for newly available `2026-06-26`
  - input rows changed from `8737` to `9005`
  - input SHA256 changed from `11322aeaee9e404fb64936aff1802be7ca111a4a3b26c8143c29becf9a154a72` to `d247c45c2d4277cdc9391a406ea50a1588f471f6e1b79f2779a7ce496df20968`
- Post-recovery live receipt:
  - `max_date`: `2026-06-26`
  - `today_unique_domains`: `67`
  - `total_rows`: `9005`
  - `bad_json_lines`: `0`
  - `empty_lines`: `0`
  - `input_sha256`: `d247c45c2d4277cdc9391a406ea50a1588f471f6e1b79f2779a7ce496df20968`
- Post-recovery June coverage:
  - date range checked: `2026-06-01` through `2026-06-26`
  - each date has `67` rows and `67` unique domains
  - June bad day count: `0`
  - June rows total: `1742`
  - all-file duplicate `(date, domain)` keys: `0`
- Scheduler proof:
  - `\CivilizationRadar-WeekdaySnapshots` was manually triggered at `2026-06-26 19:40:50`
  - final status: `Ready`
  - final last result: `0`
  - next run: `2026-06-29 18:00:00`
  - manual scheduler proof added `0` rows and left the input SHA256 unchanged
- Full-file coverage note:
  - `2026-02-10` through `2026-02-22` have fewer than `67` domains.
  - This predates the June issue and appears consistent with the early portfolio ramp-up period, so it was not treated as a current collector failure.
- Git status note:
  - The worktree was already dirty before this recovery.
  - Runtime snapshot and output artifacts remain ignored by git.
  - This task added `docs/tasks/2026-06-26_june-snapshot-recovery.md`.

## Follow-Ups

- Let the next natural `CivilizationRadar-WeekdaySnapshots` run on `2026-06-29 18:00 Asia/Taipei` confirm ordinary schedule continuity.
- If the machine is off or asleep at 18:00, `WakeToRun` remains disabled, so the host is not expected to wake itself.
