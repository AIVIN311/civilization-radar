# Task — Acceptance Gate Alignment (CI vs Promote)

Date: 2026-02-16  
Scope: acceptance entrypoint routing and ops-doc contract alignment only

## Goal

- Align promote acceptance target with CI acceptance target.
- Keep a reversible legacy fallback path.
- Fail fast when CI/promote acceptance contracts diverge, unless explicitly overridden.

## Allowed changes

- `scripts/run_acceptance_latest.py` acceptance routing and CI-contract checks only
- `README.md` acceptance entrypoint notes
- `docs/ops/RUNBOOK.md` acceptance mode notes
- `docs/ops/weekly_rhythm.md` acceptance target note
- This task log

## Do-not-touch list

- `src/persistence_v1.py` algorithms:
  - `compute_tag_persistence`
  - `classify_ers`
  - `compute_event_kernel`
- `metrics_v02.W` path assumptions
- strength / push / gate logic
- DB schema and pipeline flow

## Verification steps

1. Dynamic acceptance run (default mode):
   - `.\.venv\Scripts\python.exe scripts/run_acceptance_latest.py`
2. CI-mismatch guard:
   - run `.\.venv\Scripts\python.exe scripts/run_acceptance_latest.py --legacy-v04`
   - expect non-zero with mismatch message (CI target is v07)
3. Explicit override path:
   - `.\.venv\Scripts\python.exe scripts/run_acceptance_latest.py --legacy-v04 --allow-ci-mismatch`
4. Report contract spot-check:
   - inspect latest `output/reports/acceptance_latest_*.json`
   - verify fields: `acceptance_target`, `skip_v04_hash`, `ci_acceptance_target`, `source`
5. Script syntax check:
   - AST parse `scripts/run_acceptance_latest.py`
6. Scope check:
   - `git status --short`

## Results / notes

- Default run passed and promoted from v0.7 path:
  - report `acceptance_latest_20260216T190919Z.json`
  - `acceptance_target = v07`
  - `skip_v04_hash = true` (CI-aligned fast mode)
  - `ci_acceptance_target = v07`
  - `source = output/acceptance_v07/run_tw_a/latest`
- Mismatch guard worked as designed:
  - `--legacy-v04` without override exited with:
    - `CI/promote acceptance mismatch: ci_target=v07, promote_target=v04`
- Legacy override path worked:
  - `--legacy-v04 --allow-ci-mismatch` completed and promoted successfully
  - report `acceptance_latest_20260216T191049Z.json`
- Final state reset to default contract:
  - reran default `run_acceptance_latest.py` after legacy override test
  - newest report `acceptance_latest_20260216T191401Z.json`
  - `acceptance_target = v07`, `skip_v04_hash = true`, `ci_acceptance_target = v07`
- Syntax check passed for `scripts/run_acceptance_latest.py`.
- Scope check remained limited to planned files.

## Follow-ups

- Optional: if operation policy requires strict parity with CI flags, add a scheduled smoke check to fail when CI switches acceptance flags without corresponding ops-doc update.
