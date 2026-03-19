# Task - Blocking Operational Fixes

Date: 2026-03-19  
Scope: minimal render/promotion/acceptance fixes after Observation Baseline closeout

## Goal

- Fix the first approved post-closeout blocking operational issues without changing scoring, gate, DB schema, or pipeline flow.
- Resolve:
  - render non-fatal fallback when DB or schema is missing
  - promoted `eval_quality.json` self-containment
  - stale artifact timestamp backdating kernel output
- Keep the batch minimal, reversible, and fully verified.

## Allowed changes

- `render_dashboard_v02.py`
- `scripts/playwright/dashboard_workflow.mjs`
- `scripts/run_acceptance_latest.py`
- `scripts/run_acceptance_v07.py`
- this task log under `docs/tasks/`

## Do-not-touch list

- No changes to `src/persistence_v1.py` algorithms:
  - `compute_tag_persistence`
  - `classify_ers`
  - `compute_event_kernel`
- No gate threshold changes
- No scoring or push path changes
- No DB schema changes
- No pipeline flow rewrites
- No scheduler modifications
- No manual edits to `output/latest`

## Verification steps

1. Acceptance:

```powershell
python scripts/run_acceptance_v07.py --skip-v04-hash
```

2. Promote / latest canonicalization:

```powershell
python scripts/run_acceptance_latest.py
Get-Content .\output\latest\reports\eval_quality.json
```

3. Dashboard smoke:

```powershell
npm run playwright:dashboard
```

4. Repo cleanliness:

```powershell
git status --short
```

## Results / notes

- Implementation status: completed
- Render fix summary:
  - `render_dashboard_v02.py` now checks for `radar.db` before opening, uses read-only DB access, and renders a visible fallback note instead of failing when DB or `metrics_v02` is missing.
  - kernel timestamp alignment now uses DB `latest_ts` for `compute_event_kernel`, so stale artifact timestamps no longer backdate kernel output.
- Promote fix summary:
  - `scripts/run_acceptance_latest.py` now canonicalizes promoted `output/latest/reports/eval_quality.json` so `db_path` points to `C:\dev\civilization-radar\output\latest\radar.db`.
- Acceptance / smoke summary:
  - `scripts/run_acceptance_v07.py --skip-v04-hash` passed on `2026-03-19`, including provider-swap timestamp alignment and new non-fatal render checks for DB-missing and schema-missing cases.
  - `python scripts/run_acceptance_latest.py` passed and wrote `output/reports/acceptance_latest_20260319T085633Z.json`.
  - `output/latest/reports/eval_quality.json` parsed with `ok = true` and canonical `db_path = C:\dev\civilization-radar\output\latest\radar.db`.
  - `npm run playwright:dashboard` passed after aligning the dashboard workflow script with the current dashboard controls; summary written to `output/playwright/dashboard-workflow-summary.json`.
- Additional scope note:
  - `scripts/playwright/dashboard_workflow.mjs` was minimally updated to align the smoke-test flow with the current dashboard UI.
  - This file change is limited to verification-harness interaction updates for the current DOM and controls.
  - No runtime dashboard generation logic was changed in this file.
  - This change was included only to satisfy the required dashboard smoke verification for Batch A.
- Verification status: PASS
- Repo status after verification:
  - expected batch changes:
    - `render_dashboard_v02.py`
    - `scripts/playwright/dashboard_workflow.mjs`
    - `scripts/run_acceptance_latest.py`
    - `scripts/run_acceptance_v07.py`
    - `docs/tasks/2026-03-19_blocking-operational-fixes.md`
  - pre-existing local context state still present and intentionally untouched:
    - `M docs/context/THREE_PROJECTS_OVERVIEW.md`
    - `?? docs/context/RESEARCH_PRODUCT_LAYER_MAP.md`
    - `?? .codex/`

## Follow-ups

- If this batch passes, keep `B. v0.7.1 ops` deferred until after review of the blocking fixes batch.
