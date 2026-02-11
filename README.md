# Civilization Radar v0.5 (PR-2 in progress)

Civilization Radar is an event-driven cross-series risk propagation radar.
v0.4 is the stable base. v0.5 PR-2 adds geo_factor data-layer outputs without changing v0.4 core scoring semantics.
This repository is currently operating in observation-first mode.

## What Is New In v0.4

- Fixed snapshot schema normalization with missing/extra field markers.
- Canonical series + aliases from one source: `config/series_aliases.json`.
- Event strength explain payload (`strength_explain_json`) persisted in DB.
- Chain push split into `base_score`, `boosted_score`, `delta_boost`.
- Event explainability on chain edges (`src_event_*`, `matched_signals`).
- Half-life is configurable by CLI or env (`RADAR_EVENT_HALF_LIFE_DAYS`).
- Strict quality gate (`scripts/eval_quality.py`) with non-zero exit on critical issues.
- All generated artifacts now use a stabilized output layout with `output/latest/`.

## v0.5 PR-2 (Geo Factor Data Layer)

- SSOT path is fixed: `config/geo_profiles_v1.json`.
- Active geo profile is single-select per run (`--geo-profile`, default `tw`).
- New chain outputs (non-interfering):
  - `geo_factor`
  - `geo_factor_explain_json`
  - `tw_rank_score`
  - `tw_rank_explain_json`
- `tw_rank_score` uses:
  - `tw_rank_score = boosted_push * (1 + geo_factor)`
  - `base_push / boosted_push / delta_boost` semantics remain unchanged.

## Environment

```bash
cp env.example .env
```

Key optional env vars:

- `RADAR_OUTPUT_DIR` (default `output`)
- `RADAR_EVENT_HALF_LIFE_DAYS` (default `7`)

## Full Pipeline (v0.4)

```bash
python run_pipeline_50.py --output-dir output --half-life-days 7 --geo-profile tw --input-snapshots input/snapshots.jsonl
```

Output:

- DB: `output/latest/radar.db`
- Dashboard: `output/latest/dashboard_v04.html`
- Quality report: `output/reports/eval_quality_<run_id>.json`

## One-command Run

`run_pipeline_50.py` writes full artifacts under:

- `output/runs/<YYYYMMDDTHHMMSSZ>/`
- promotes successful run to `output/latest/`

## Long-term Automation Status (Ops)

Current assessment:

- ✅ Automation scripts and schedule definitions are present in repo.
- ⚠️ Whether automation is **already running in production** depends on host-level Windows Task Scheduler registration.

Expected scheduled tasks (Windows host, Asia/Taipei timezone):

- `CivilizationRadar-WeekdaySnapshots` (Mon-Thu 18:00)
- `CivilizationRadar-FridayPromote` (Fri 18:00)
- `CivilizationRadar-MonthEndPipelineTag` (Daily 19:00, self-gated for month-end)

Quick verification commands (PowerShell on the Windows runner):

```powershell
# list tasks
schtasks /Query /TN "CivilizationRadar-WeekdaySnapshots" /V /FO LIST
schtasks /Query /TN "CivilizationRadar-FridayPromote" /V /FO LIST
schtasks /Query /TN "CivilizationRadar-MonthEndPipelineTag" /V /FO LIST

# (re)register all three tasks from repo scripts
powershell -ExecutionPolicy Bypass -File .\ops\register_weekly_tasks.ps1
```

Recent-run evidence to collect when checking "is long-term collection active":

- `input/snapshots.jsonl` keeps appending on weekdays
- new `output/reports/acceptance_latest_*.json` appears after Friday promote
- `output/latest/reports/eval_quality.json` has `ok: true`

If these artifacts stop updating, run:

- `ops/collect_snapshots_weekday.ps1` for collection repair
- `ops/promote_latest.ps1` for Friday promotion repair
- `ops/month_end_release.ps1` for month-end repair

## Fixed Regression / Acceptance

Fixture:

- `input/snapshots.sample.jsonl`

Run deterministic acceptance:

```bash
python scripts/run_acceptance_v04.py
python scripts/run_acceptance_latest.py
```

This validates:

- schema fixedness and missing/extra markers
- alias canonicalization (`identity* -> identity_data`)
- cf-vs-origin strength gap
- Top-3 explain columns on chain edges
- `base/boosted/delta` invariants
- half-life sensitivity (`3` vs `14`)
- L1/L2/L3 propagation consistency
- eval gate fail on bad ts order
- deterministic output hash across two runs

## Notes

- The dashboard has three synchronized lists: Domain / Events / Chain.
- `Only L3` filter applies across all three lists.
- Chain Top-3 rows expose event source, strength, decayed strength, boost, and matched signals.
- Cleanup helper:
  - `python scripts/clean_output.py`
  - `python scripts/clean_output.py --nuke`

## Documentation Completeness Checklist

This README currently covers:

- architecture + version scope (v0.4 base, v0.5 PR-2 data-layer extension)
- one-command and full-pipeline execution
- acceptance regression entry points
- long-term automation scripts and verification checklist

If you want fully "ops-ready" docs, add these next:

- `.env` key-by-key reference with examples
- failure-playbook examples (common stack traces + fixes)
- data retention/rotation policy for `output/runs/` and `input/snapshots.jsonl`
- dashboard field dictionary for `geo_factor` and `tw_rank_*`
