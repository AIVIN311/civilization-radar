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
