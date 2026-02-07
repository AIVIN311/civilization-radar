# Civilization Radar v0.5 (PR-2 in progress)

Civilization Radar is an event-driven cross-series risk propagation radar.
v0.4 is the stable base. v0.5 PR-2 adds geo_factor data-layer outputs without changing v0.4 core scoring semantics.

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
