# Civilization Radar Status

## 1. Current Stage
- Stage: `Observation Baseline`.
- Operating mode: minimal changes, verification-first operations, and deterministic maintenance.
- Scope policy: fix blocking operational issues only; avoid feature expansion unless explicitly approved.

## 2. When To Check
- Mon-Thu: check snapshot collection task and confirm `input/snapshots.jsonl` keeps moving forward.
- Fri: check promote task and confirm acceptance refresh to `output/latest`.
- Month-end: check monthly pipeline/tag task and confirm release pipeline + quality gate outputs are fresh.

## 3. What Counts As Abnormal
- Any scheduled task has `Last Result != 0`.
- `input/snapshots.jsonl` timestamp does not advance as expected.
- `output/latest/radar.db` is not refreshed after promote/month-end run.
- `output/latest/reports/eval_quality.json` is missing or `ok != true`.
- Any task `Task To Run` path is not under `C:\dev\civilization-radar\ops\*.ps1`.

## 4. Observation KPI (30-day)
- KPI-1 (quality gate): over a 30-day window, `output/latest/reports/eval_quality.json` exists and `ok = true`, with at least one refresh after each Friday promote.
- KPI-2 (data continuity): `input/snapshots.jsonl` gains at least one new row every day, validated by dual checks (`mtime` + the latest row `date`/`ts`).
- KPI-3 (promote freshness): after each Friday promote run, `output/latest/radar.db` mtime is later than promote start time (or consistent with the newest `output/reports/acceptance_latest_*.json` timestamp).
