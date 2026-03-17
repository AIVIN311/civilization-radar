# civilization-radar current status

Status snapshot: 2026-03-17

## Current Stage

`civilization-radar` is in `v0.7 Observation Baseline`. The repo is operating in a minimal-change, verification-first mode where deterministic maintenance matters more than new features.

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

As of `2026-03-17`, the repo is at a closeout scaffold stop point, not formal closeout completion.

- closeout date remains `2026-03-18`
- today is docs-only preparation
- final receipt is intentionally still unfilled
- no implementation work is approved in the stop-point batch

Approved next-step rule:

- on `2026-03-18`, run closeout final receipt verification only
- if closeout passes, open `A. blocking operational fixes`
- if closeout fails, switch to incident / recovery triage
- keep `B. v0.7.1 ops` deferred until after batch A

## Current Issues

Three verified operational issues are currently recorded but intentionally deferred until after closeout:

- render non-fatal fallback is broken when DB or schema is missing
- promoted `eval_quality.json` is not self-contained because it points at an acceptance-run DB path
- artifact-first render can backdate explanatory kernel output when a valid stale artifact is present

## Next Step

The next approved action is not implementation today. The next approved action is the `2026-03-18` closeout final receipt verification. Only after a passing closeout should the repo open `A. blocking operational fixes`.

## Deferred

- `B. v0.7.1 ops` headless scheduler hardening
- observer rollout as a mainline implementation topic
- any changes to scoring, gate, kernel, persistence logic, pipeline flow, or DB schema

## GPT Notes

- Prioritize `docs/ops/*` when questions involve operations or baseline policy.
- Treat task files as time-scoped status artifacts, not permanent architecture docs.
- Do not recommend code changes that touch scoring, kernel, gate, persistence, or schema unless the prompt explicitly authorizes that class of work.
- When discussing current status, include the concrete date `2026-03-17` or `2026-03-18` so closeout timing stays clear.
