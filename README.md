# Civilization Radar v0.4

Civilization Radar is an event-driven cross-series risk propagation radar.
v0.4 focuses on deterministic outputs, explainability, and strict release gates.

## What Is New In v0.4

- Fixed snapshot schema normalization with missing/extra field markers.
- Canonical series + aliases from one source: `config/series_aliases.json`.
- Event strength explain payload (`strength_explain_json`) persisted in DB.
- Chain push split into `base_score`, `boosted_score`, `delta_boost`.
- Event explainability on chain edges (`src_event_*`, `matched_signals`).
- Half-life is configurable by CLI or env (`RADAR_EVENT_HALF_LIFE_DAYS`).
- Strict quality gate (`scripts/eval_quality.py`) with non-zero exit on critical issues.
- All generated artifacts now default to `output/` (`output/radar.db`, `output/dashboard_v04.html`).

## Environment

```bash
cp env.example .env
```

Key optional env vars:

- `RADAR_OUTPUT_DIR` (default `output`)
- `RADAR_EVENT_HALF_LIFE_DAYS` (default `7`)

## Full Pipeline (v0.4)

```bash
python scripts/apply_sql_migrations.py --output-dir output
python seed_from_snapshots.py --input input/snapshots.jsonl --output-dir output
python upgrade_to_v02.py --output-dir output
python scripts/derive_events_from_daily.py --input output/daily_snapshots.jsonl --output-dir output
python scripts/load_events_into_db.py --output-dir output
python build_chain_matrix_v10.py --half-life-days 7 --output-dir output
python upgrade_to_v03_chain.py --output-dir output
python render_dashboard_v02.py --half-life-days 7 --output-dir output
python scripts/eval_quality.py --missing-ratio-threshold 0.0 --output-dir output
```

Output:

- DB: `output/radar.db`
- Dashboard: `output/dashboard_v04.html`
- Quality report: `output/reports/eval_quality.json`

## One-command Run

```bash
python run_pipeline_50.py --output-dir output --half-life-days 7 --input-snapshots input/snapshots.jsonl
```

## Fixed Regression / Acceptance

Fixture:

- `input/snapshots.sample.jsonl`

Run deterministic acceptance:

```bash
python scripts/run_acceptance_v04.py
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
