# Civilization Radar — v0.7 Observation Baseline

Civilization Radar is an event-driven cross-series risk propagation radar.
The project has moved from experiment-heavy iteration into observation-first operations.

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
python scripts/run_acceptance_v07.py --skip-v04-hash
```

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
2. `docs/README.md` (document index)
3. `ops/OBSERVATION_BASELINE.md`
4. `CIVILIZATION_RADAR_STATUS.md`
5. `docs/releases/v0.4.md` to `docs/releases/v0.7.md`

Key links:
- Status/KPI: `CIVILIZATION_RADAR_STATUS.md`
- Ops rhythm: `ops/weekly_rhythm.md`
- Acceptance protocol: `ops/radar_acceptance_protocol.md`
- Non-interference rules: `ops/radar_non_interference_rules.md`
