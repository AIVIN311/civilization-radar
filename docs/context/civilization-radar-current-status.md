# civilization-radar current status

Status snapshot: 2026-03-20

## Current Stage

`civilization-radar` remains in `v0.7 Observation Baseline`. The repo is still operating in a minimal-change, verification-first mode where deterministic maintenance matters more than new features. Within that stage, `v0.7.1 ops` slice 1 is now completed and naturally validated, but `v0.7.1 ops` as a whole is not complete.

## What It Does

The system is an event-driven cross-series risk propagation radar. Its core operating model is:

- collect runtime snapshots
- run acceptance
- promote accepted artifacts into `output/latest`
- use canonical outputs for comparison and reporting

Primary canonical outputs include:

- `output/latest/radar.db`
- `output/latest/dashboard_v04.html`
- `output/latest/reports/eval_quality.json`
- `output/reports/acceptance_latest_<timestamp>.json`

## Canonical Docs

- `README.md`
- `AGENTS.md`
- `docs/ops/BASELINE.md`
- `docs/ops/RUNBOOK.md`
- `docs/architecture/OUTPUTS.md`
- `docs/metrics/EVAL.md`
- `docs/RADAR_AGENT_CONTRACT_v0.1.md`
- `docs/OBSERVER_CONTRACT_v0.1.md`

Time-scoped context currently in use:

- `docs/tasks/2026-03-18_observation-baseline-closeout.md`
- `docs/tasks/2026-03-18_post-closeout-triage.md`
- `docs/tasks/2026-03-19_blocking-operational-fixes.md`
- `docs/tasks/2026-03-20_30d-baseline-findings.md`
- `docs/tasks/2026-03-20_v0.7.1-headless-scheduler-hardening.md`
- `docs/tasks/2026-03-20_v0.7.1-headless-scheduler-hardening-implementation.md`
- `docs/tasks/2026-03-20_v0.7.1-natural-window-receipt.md`

## Operational Rhythm

Default scheduler cadence on the host is:

- Mon-Thu 18:00: `CivilizationRadar-WeekdaySnapshots`
- Fri 18:00: `CivilizationRadar-FridayPromote`
- Daily 19:00: `CivilizationRadar-MonthEndPipelineTag`

Operational rules that matter most:

- `input/snapshots.jsonl` is a runtime artifact, not a tracked source file
- render should be artifact-first where possible
- render must remain non-fatal when artifacts or inputs are missing
- scoring, gate, kernel, persistence logic, and DB schema are baseline-sensitive

## Current Closeout Status

Observation Baseline closeout is complete, and the first `v0.7.1 ops` slice is now closed as completed history.

- closeout completed on `2026-03-18` and was recorded in commit `4119d66`
- `A. blocking operational fixes` completed on `2026-03-19` and was recorded in commit `ebb3e34`
- the 30-day findings memo was recorded in commit `f1900d9`
- the first `v0.7.1 ops` slice definition was recorded in commit `ca1ee3a`
- slice 1 implementation was recorded in commit `8587a68`
- slice 1 was naturally validated in production cadence on `2026-03-20`
- `Observation Baseline` remains the active top-level stage label after slice 1 validation
- `v0.7.1 ops` slice 2 has not been opened

## Current Issues

The three blocking operational issues carried out of closeout were resolved in Batch A (`ebb3e34`):

- render now remains non-fatal when DB or schema is missing
- promoted `eval_quality.json` is now self-contained through canonical `output/latest/radar.db`
- kernel timestamp alignment no longer backdates explanatory output when a stale artifact is present

There is no new implementation batch opened by this file. The remaining deferred operational topics are the natural month-end proof for same-user background mode and the question of whether to open a later `v0.7.1 ops` slice.

## Next Step

Slice 1 is complete and naturally validated.

This status file does not open slice 2 on its own. The next repo decision point is:

- continue observing the natural month-end window to capture full headless month-end `git push` proof
- or re-read the 30-day findings and explicitly decide whether to open a new `v0.7.1 ops` slice

## Deferred

- full headless month-end `git push` proof at the natural month-end window
- `v0.7.1 ops` slice 2 (still unopened)
- observer rollout as a mainline implementation topic
- any changes to scoring, gate, kernel, persistence logic, pipeline flow, or DB schema

## GPT Notes

- Prioritize `docs/ops/*` when questions involve operations or baseline policy.
- Treat task files as time-scoped status artifacts, not permanent architecture docs.
- Do not recommend code changes that touch scoring, kernel, gate, persistence, or schema unless the prompt explicitly authorizes that class of work.
- When discussing current status, include the concrete dates `2026-03-18`, `2026-03-19`, and `2026-03-20` so the closeout, Batch A, and slice 1 natural-validation checkpoints stay clear.
