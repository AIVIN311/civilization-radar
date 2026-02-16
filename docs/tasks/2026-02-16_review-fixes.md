# Task — Review Follow-up Minimal Fixes

Date: 2026-02-16  
Scope: acceptance wrapper parameter consistency, legacy script hygiene, syntax safety

## Goal

- Fix concrete defects identified during repository-wide review without changing scoring/kernel/gate behavior.
- Keep changes minimal and reversible.

## Allowed changes

- `scripts/run_acceptance_v04.py` CLI/output-root wiring only.
- `scripts/run_acceptance_latest.py` argument forwarding only.
- `pressure_flow.py` syntax typo fix only.
- `ops/promote_latest.ps1` dead-code cleanup after `exit 0`.
- `ops/month_end_release.ps1` trailing artifact line cleanup.
- This task log file.

## Do-not-touch list

- `src/persistence_v1.py` algorithms:
  - `compute_tag_persistence`
  - `classify_ers`
  - `compute_event_kernel`
- `metrics_v02.W` path assumptions
- strength / push / gate logic
- DB schema and pipeline flow

## Verification steps

1. Confirm modified files are limited to planned scope:
   - `git status --short`
2. Python parse check for changed Python files:
   - `python` AST parse for:
     - `scripts/run_acceptance_v04.py`
     - `scripts/run_acceptance_latest.py`
     - `pressure_flow.py`
3. Repository-wide Python parse check:
   - AST parse all `*.py` (excluding `.venv` and `node_modules`)
4. Spot-check output-root handoff:
   - confirm `scripts/run_acceptance_latest.py` passes `--output-root`
   - confirm `scripts/run_acceptance_v04.py` accepts and applies `--output-root`
5. Spot-check ops script cleanup:
   - verify no commands remain after `exit 0` in `ops/promote_latest.ps1`
   - verify no stray trailing token in `ops/month_end_release.ps1`

## Results / notes

- Changes were constrained to the planned files and this task log.
- `git status --short` (scope check):
  - `M ops/month_end_release.ps1`
  - `M ops/promote_latest.ps1`
  - `M pressure_flow.py`
  - `M scripts/run_acceptance_latest.py`
  - `M scripts/run_acceptance_v04.py`
  - `?? docs/tasks/2026-02-16_review-fixes.md`
- `pressure_flow.py` syntax error (`...["W"]m`) fixed to valid expression.
- Acceptance wrapper now forwards output root and v0.4 acceptance script now honors it.
- Dead code / stray line removed from the two ops scripts.
- Changed-file AST parse passed (`syntax_ok 3`).
- Repo-wide AST parse passed (`bad_count 0`).
- No scoring/kernel/gate/persistence algorithm paths were modified.

## Follow-ups

- Optional: align operational acceptance target (`run_acceptance_latest.py`) with v0.7 CI strategy in a dedicated, explicit baseline decision task.
