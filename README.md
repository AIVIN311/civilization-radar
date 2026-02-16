# Civilization Radar — v0.7 Observation Baseline

Civilization Radar is an event-driven cross-series risk propagation radar.
The project has moved from experiment-heavy iteration into observation-first operations.

## For Agents / Baseline Ops

Route lock (single onboarding path):
1. `README.md`
2. `AGENTS.md`
3. `docs/ops/RUNBOOK.md`
4. `docs/architecture/OUTPUTS.md` + `docs/metrics/EVAL.md`
5. `docs/tasks/2026-02-12_route-lock.md`

Direct links:
- `AGENTS.md`
- `docs/ops/BASELINE.md`
- `docs/ops/RUNBOOK.md`

Ops docs contract:
- Canonical operations docs live in `docs/ops/*`.
- `ops/*.md` files are allowed only as legacy tombstones (redirect notes, no canonical body).
- Runtime scripts remain in `ops/*.ps1`.

## Current Stage

This repository is now in `Observation Baseline` mode.

Principles:
- Avoid unnecessary feature expansion.
- Prefer deterministic verification over new behavior changes.
- Treat operational reliability as the primary delivery target.

## Core Pipeline Contract

Primary pipeline command:

```bash
python run_pipeline_50.py --output-dir output --half-life-days 7 --geo-profile tw --input-snapshots input/snapshots.jsonl
```

Primary outputs:
- `output/latest/radar.db`
- `output/latest/dashboard_v04.html`
- `output/latest/reports/eval_quality.json`
- `output/reports/acceptance_latest_<timestamp>.json`

Acceptance entry points:

```bash
python scripts/run_acceptance_v04.py
python scripts/run_acceptance_latest.py
python scripts/run_acceptance_latest.py --legacy-v04
python scripts/run_acceptance_v07.py --skip-v04-hash
```

`run_acceptance_latest.py` default contract:
- uses v0.7 acceptance in CI-aligned fast mode (`--skip-v04-hash`)
- can be switched to full v0.7 via `--full-v07`
- keeps explicit legacy fallback via `--legacy-v04`

## Runtime Data Policy

`input/snapshots.jsonl` is a runtime artifact.

- It is maintained by scheduled collection jobs.
- It is intentionally not tracked in Git.
- Sample fixtures remain tracked:
  - `input/snapshots.sample.jsonl`
  - `input/snapshots.geo.sample.jsonl`

## Operations Rhythm

Default operational cadence (Asia/Taipei host time):
- Mon-Thu 18:00: `CivilizationRadar-WeekdaySnapshots`
- Fri 18:00: `CivilizationRadar-FridayPromote`
- Daily 19:00 (self-gated month-end): `CivilizationRadar-MonthEndPipelineTag`

Repair commands:
- `powershell -ExecutionPolicy Bypass -File .\ops\collect_snapshots_weekday.ps1`
- `powershell -ExecutionPolicy Bypass -File .\ops\promote_latest.ps1`
- `powershell -ExecutionPolicy Bypass -File .\ops\month_end_release.ps1`

## Health Checks

Minimum checks:

```powershell
schtasks /Query /TN "CivilizationRadar-WeekdaySnapshots" /V /FO LIST
schtasks /Query /TN "CivilizationRadar-FridayPromote" /V /FO LIST
schtasks /Query /TN "CivilizationRadar-MonthEndPipelineTag" /V /FO LIST
```

Pass criteria:
- Task `Last Result = 0`
- `output/latest/reports/eval_quality.json` exists and `ok = true`
- `output/latest/radar.db` refreshes after promote/month-end runs
- New `output/reports/acceptance_latest_*.json` appears after promote

## Known Operational Constraints

Current scheduler mode is still interactive:
- `Logon Mode`: `Interactive only`
- XML `LogonType`: `InteractiveToken`
- `WakeToRun`: not enabled

Planned follow-up (`v0.7.1 ops`):
- move to headless-capable scheduler mode
- evaluate enabling wake-to-run based on host policy

## Documentation Map

Canonical reading order:
1. `README.md` (this file)
2. `AGENTS.md`
3. `docs/ops/RUNBOOK.md`
4. `docs/architecture/OUTPUTS.md` + `docs/metrics/EVAL.md`
5. `docs/tasks/2026-02-12_route-lock.md`

Key links:
- Baseline definition: `docs/ops/BASELINE.md`
- Document index: `docs/README.md`
- Status/KPI: `CIVILIZATION_RADAR_STATUS.md`
- Release notes: `docs/releases/v0.4.md` to `docs/releases/v0.7.md`
