# TASK - Observer v0.1 Bootstrap

Date: 2026-02-28  
Scope: `ops/observer/observer_v01.py` initial implementation (v5 spec)

## Goal

Implement Observer v0.1 as a read-only observer script that:
- reads only approved inputs,
- writes only `output/observer` artifacts,
- emits deterministic report/summary ordering,
- always writes FAIL report+summary before exit code `1` on failure.

## Allowed

- Add `ops/observer/observer_v01.py`
- Add task log documentation under `docs/tasks/`
- No changes to scoring/gate/kernel/pipeline logic

## Do-not-touch

- `persistence_v1.py` algorithms:
  - `compute_tag_persistence`
  - `classify_ers`
  - `compute_event_kernel`
- `metrics_v02.W` path assumptions
- strength/push/gate routing
- DB schema and pipeline main flow
- any mutation of `output/latest` artifacts

## Verification

1. Syntax check:
   - `python -m py_compile ops/observer/observer_v01.py`
2. Failure-path behavior (missing required configs/inputs in current workspace):
   - `python ops/observer/observer_v01.py --domain-count 67`
   - expected: exit code `1`, plus generated:
     - `output/observer/observer_report_<timestamp>.json`
     - `output/observer/observer_summary_<date>.txt`
3. Deterministic ordering check (except timestamp fields):
   - run script twice with same args
   - compare JSON reports after removing `generated_at` and `run_id`
   - expected: identical payload
4. Git impact check:
   - `git status --short`
   - expected tracked changes only under `ops/observer/` and docs task file.

## Results

- `py_compile`: passed.
- Failure-path run:
  - exit code `1` confirmed.
  - FAIL report and summary generated under `output/observer/`.
- Deterministic check:
  - two consecutive reports compared equal after removing timestamps (`same_wo_timestamps = True`).
- Scope safety:
  - no changes to baseline-sensitive runtime logic, schema, or pipeline flow.
