# civilization-radar current status

Status snapshot: 2026-03-19

## Current Stage

`civilization-radar` is in `v0.7 Observation Baseline`. The repo is still operating in a minimal-change, verification-first mode where deterministic maintenance matters more than new features, but the closeout checkpoint and first post-closeout operational batch are now both recorded history.

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

Observation Baseline closeout is complete.

- closeout completed on `2026-03-18` with result `PASS`
- the formal closeout receipt was recorded in commit `4119d66`
- `A. blocking operational fixes` completed on `2026-03-19`
- the completed Batch A checkpoint was recorded in commit `ebb3e34`
- `Observation Baseline` remains the active stage label after Batch A
- `B. v0.7.1 ops` remains deferred pending an explicit next decision

## Current Issues

The three blocking operational issues carried out of closeout were resolved in Batch A (`ebb3e34`):

- render now remains non-fatal when DB or schema is missing
- promoted `eval_quality.json` is now self-contained through canonical `output/latest/radar.db`
- kernel timestamp alignment no longer backdates explanatory output when a stale artifact is present

There is no new implementation batch opened by this file. The remaining deferred operational topic is still `B. v0.7.1 ops`.

## Next Step

Batch A is complete.

This status file does not open a new batch on its own. The next repo decision is to review the completed closeout and Batch A checkpoints, then explicitly choose the next implementation batch, with `B. v0.7.1 ops` still the leading deferred candidate.

## Deferred

- `B. v0.7.1 ops` headless scheduler hardening
- observer rollout as a mainline implementation topic
- any changes to scoring, gate, kernel, persistence logic, pipeline flow, or DB schema

## GPT Notes

- Prioritize `docs/ops/*` when questions involve operations or baseline policy.
- Treat task files as time-scoped status artifacts, not permanent architecture docs.
- Do not recommend code changes that touch scoring, kernel, gate, persistence, or schema unless the prompt explicitly authorizes that class of work.
- When discussing current status, include the concrete dates `2026-03-18` and `2026-03-19` so the closeout and Batch A checkpoints stay clear.
