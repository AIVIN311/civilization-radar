# 2026-04-01 month-end canonical trust

- Goal
  - Restore trustworthy canonical month-end behavior for `output/latest` by fixing false-positive quality failures and preventing month-end promote from getting ahead of its proof trail.

- Allowed changes
  - `seed_from_snapshots.py`
  - `ops/month_end_release.ps1`
  - `scripts/run_acceptance_v04.py`
  - task log for verification

- Do-not-touch list
  - scoring logic
  - kernel logic
  - persistence interpretation outside canonical snapshot ordering
  - DB schema
  - unrelated scheduler behavior
  - unrelated local worktree drift

- Verification steps
  - `python scripts/run_acceptance_v04.py`
  - `python scripts/eval_quality.py --output-dir output/latest`
  - `powershell -ExecutionPolicy Bypass -File .\ops\month_end_release.ps1 -ForceMonthEnd -SkipTagPush`
  - `python scripts/eval_quality.py --output-dir output/latest`
  - inspect newest `output/reports/month_end_*.json`
  - inspect `output/latest/reports/eval_quality.json`
  - inspect `output/latest/reports/eval_quality_monthly.json`

- Results / notes
  - `run_acceptance_v04.py` passed after adding targeted checks:
    - reversed/backfill input order no longer trips `ts_out_of_order`
    - minimal live-shape rows no longer create trust-missing markers
    - intentionally bad timestamp regression still fails `ts_out_of_order`
  - Forced local month-end repair completed successfully with `-SkipTagPush`.
  - New month-end receipt written at `output/reports/month_end_20260401T150008Z.json`.
  - Canonical latest now reports:
    - `ok = true`
    - `ts_out_of_order = 0`
    - `missing_fields_ratio_abnormal = 0`
    - `db_path = C:\dev\civilization-radar\output\latest\radar.db`
  - Canonical monthly quality artifact now exists at `output/latest/reports/eval_quality_monthly.json`.
  - Receipt status is `success_no_push`, so local canonical state is repaired without claiming repo-level tag-push proof.

- Follow-ups
  - If explicit repo-level month-end proof is desired later, run the month-end path without `-SkipTagPush` in a real proof window or with explicit operator approval.
