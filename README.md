# Civilization Radar

Civilization Radar is an event-driven cross-series risk propagation radar.
It converts domain-level traffic signals into event strength, maps them into inter-series push dynamics, and renders an explainable dashboard showing who is pushing whom, by how much, and whether events amplified the propagation.

## Core Capabilities
- Snapshot generation and ingestion (`input/snapshots.jsonl` -> `metrics_v02`)
- Daily event derivation (`output/daily_snapshots.jsonl` -> `output/events_derived.jsonl`)
- Event persistence into `events_v01` (including `strength`, `series_raw`, resolved `series`)
- Chain matrix computation (with event boost and time decay)
- Explainable dashboard rendering (Domain / Series / Top-3 propagation edges)

## Project Structure (Key Files)
- `gen_snapshots_50.py`: generate simulated snapshots
- `seed_from_snapshots.py`: ingest snapshots into SQLite
- `upgrade_to_v02.py`: build `metrics_v02` and v02 views
- `scripts/derive_events_from_daily.py`: derive events from daily snapshots
- `scripts/load_events_into_db.py`: load events into `events_v01`
- `build_chain_matrix_v10.py`: compute chain edges / series chain (with decay)
- `render_dashboard_v02.py`: render `dashboard_v02.html`
- `scripts/apply_sql_migrations.py`: apply `events_v01` schema and related views

## Quick Start

### Option A: Basic One-Command Pipeline
```bash
python run_pipeline_50.py
```
This runs:
1. `gen_snapshots_50.py`
2. `seed_from_snapshots.py`
3. `upgrade_to_v02.py`
4. `render_dashboard_v02.py`

### Option B: Full Event + Chain Pipeline (Recommended)
```bash
python scripts/apply_sql_migrations.py
python gen_snapshots_50.py
python seed_from_snapshots.py
python upgrade_to_v02.py
python scripts/derive_events_from_daily.py
python scripts/load_events_into_db.py
python build_chain_matrix_v10.py
python render_dashboard_v02.py
```

Outputs:
- Database: `radar.db`
- Dashboard: `dashboard_v02.html`

## Data Flow and Semantics
1. `metrics_v02`: domain-level time-series risk signals (W/A/etc.)
2. `events_v01`: derived daily events (type/ratio/delta/strength)
3. `chain_edges_v10`, `chain_edges_decay_latest`: inter-series propagation edges
4. `series_chain_v10`, `series_chain_decay_latest`: series-level rollups (`W_avg`/`W_proj`/`chain_flag`)

## Key Formulas (Current Version)

### 1) Event Strength (`src/event_strength.py`)
`event_strength` compresses anomaly ratio, origin/cf composition, and volume into a `0~10` score.

### 2) Event Boost (`src/chain_event_boost.py`)
```text
event_boost = 1 + log1p(strength) / 2
```

### 3) Time Decay (`build_chain_matrix_v10.py`)
Event strength decays with a half-life (default 7 days):
```text
decayed_strength = strength * exp(-ln(2) * age_days / half_life_days)
```

### 4) Chain Push (v1.1)
```text
push = corr * dW * event_boost(decayed_strength)
```

The dashboard also shows:
- `base_score` (structural push)
- `boosted_score` (event-amplified push)

## How to Read the Dashboard

### Domain Table
- `Event` column format: `event_type | s=<strength> | req_key`
- Displays `—` when no event is available

### Series Table
- `base_score`: push before event amplification
- `boosted_score`: push after event amplification

### Top-3 Expansion
- Shows `event_boost = x...`
- Each row shows `dst_boost_applied: x...`

## Newly Added Domains
These 4 domains are included and active in snapshots/dashboard:
- `algorithmicallocation.ai`
- `algorithmicallocation.systems`
- `algorithmiclegitimacy.ai`
- `syntheticsolvency.ai`

## Troubleshooting

### 1) `event_boost` stays `x1.00`
Usually means no matching effective event exists for that series, or event date is ahead of the current metrics timestamp (future event ignored by decay logic).

### 2) Duplicate column warning during migration
`scripts/apply_sql_migrations.py` is idempotent and safely ignores duplicate-column errors.

### 3) Import path errors for `src.*`
Main scripts include repo-root `sys.path` fallback; run commands from repo root.

## Version Positioning
Current state is effectively `v0.3`:
- Event-driven chain push
- Event boost with time decay
- Explainable dashboard (`base_score` vs `boosted_score` + Top-3 annotations)
