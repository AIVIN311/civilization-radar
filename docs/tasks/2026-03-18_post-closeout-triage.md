# Task - Post-Closeout Triage

Date: 2026-03-18  
Scope: docs-only decision artifact for the first post-closeout implementation batch

## Goal

- Decide the first minimal, reversible implementation batch after Observation Baseline closeout.
- Keep the decision aligned with current repo policy: minimal changes, verification-first, deterministic maintenance.
- Separate contract-level operational fixes from planned ops hardening.
- Apply this note only if closeout passes; if closeout fails, switch to incident / recovery triage instead of opening the next implementation batch.

## Allowed changes

- Docs-only updates under `docs/tasks/`
- Read-only use of:
  - `docs/tasks/2026-03-18_observation-baseline-closeout.md`
  - `README.md`
  - `CIVILIZATION_RADAR_STATUS.md`
  - `docs/ops/BASELINE.md`
  - current runtime receipts and acceptance outputs

## Do-not-touch list

- No runtime code changes in this batch
- No scheduler modifications in this batch
- No repair actions in this batch
- No changes to pipeline flow, DB schema, scoring, kernel, persistence, or observer scope
- `src/persistence_v1.py` algorithms:
  - `compute_tag_persistence`
  - `classify_ers`
  - `compute_event_kernel`
- `metrics_v02.W` path assumptions
- strength / push / gate routing

## Decision inputs

- Observation Baseline policy remains active:
  - `README.md` says the repo is still in `Observation Baseline` mode
  - `CIVILIZATION_RADAR_STATUS.md` says the operating mode is `minimal changes, verification-first operations, and deterministic maintenance`
  - status policy says to fix blocking operational issues only and avoid feature expansion unless explicitly approved
- Pre-closeout runtime health is currently good:
  - scheduler tasks report `Last Result = 0`
  - `output/live/live_snapshot_status.json` is fresh through `2026-03-17`
  - `output/latest/reports/eval_quality.json` exists and reports `ok = true`
- Known residual risks from review remain open:
  - `render non-fatal fallback broken`
  - `promoted eval_quality.json not self-contained`
  - `artifact-first timestamp can backdate kernel output`
- Current evidence for contract-level risk:
  - `output/latest/reports/eval_quality.json` currently embeds `db_path = C:\dev\civilization-radar\output\acceptance_v07\run_tw_a\runs\20260313T100005Z\radar.db`, so the promoted latest receipt is not self-contained
  - `render_dashboard_v02.py` computes `persistence_latest_ts` from the delta/persistence source and passes it into `compute_event_kernel`
  - `src/persistence_v1.py` filters active kernel rows by exact `latest_ts`, so a stale artifact timestamp can backdate derived kernel selection even when newer DB rows exist
  - `docs/architecture/OUTPUTS.md` and `docs/tasks/2026-02-12_dt-artifactfirst.md` require safe fallback and non-fatal render behavior

## Recommended next batch: A. blocking operational fixes

## Reasoning

- The baseline policy currently prioritizes blocking operational integrity over new improvement work.
- The three residual risks are contract-level issues because they weaken trust in canonical artifacts or violate stated output/render guarantees.
- `render non-fatal fallback broken` conflicts with the rule that render must not crash when artifacts or inputs are missing or invalid.
- `promoted eval_quality.json not self-contained` weakens auditability of `output/latest`, because the promoted quality receipt points at an acceptance-run DB path instead of standing on its own canonical latest reference.
- `artifact-first timestamp can backdate kernel output` weakens comparability of derived artifacts by allowing a stale artifact timestamp to drive kernel selection against older rows.
- By contrast, `v0.7.1 ops` is useful and already planned, but current scheduler operation is stable enough that it is not the first integrity blocker.

## Deferred batch: B. v0.7.1 ops

## Why deferred now

- `v0.7.1 ops` remains the correct planned follow-up for headless-capable scheduler hardening.
- It improves operator reliability, but it does not directly resolve the contract-level trust issues recorded above.
- Current scheduler state is functioning:
  - `CivilizationRadar-WeekdaySnapshots` last result `0`
  - `CivilizationRadar-FridayPromote` last result `0`
  - `CivilizationRadar-MonthEndPipelineTag` last result `0`
- For the current stage, the cleaner sequence is:
  - complete closeout receipt
  - if closeout passes, execute `A. blocking operational fixes`
  - if closeout fails, switch to incident / recovery triage and do not open batch A yet
  - after batch A, re-evaluate and then queue `B. v0.7.1 ops`

## Verification

- This note is docs-only.
- Recommendation is based on existing repo policy, current runtime receipts, and already identified residual risks.
- `git status --short` after this batch should show only the new docs task files plus any pre-existing local operator noise such as `.codex/`.
