# Civilization Radar Purpose and Boundary

Status: stable positioning note. This document defines project direction; it does not change the v0.7 baseline, scoring, gate, kernel, persistence, schema, or runtime pipeline.

## Purpose

Civilization Radar is the observation and verification layer for the concept network published by `concept-markers`.

Its purpose is to turn runtime snapshots into a long-running, reproducible observation record and to detect:

- structural health and data-continuity changes
- statistical deviations from the observation baseline
- persistence within a series
- cross-series propagation or concentration patterns
- recurring patterns that remain visible across independent time windows

The primary output is evidence with a defined window, provenance, fingerprint, and verification status.

## What Radar Is Not

Radar is not a market-prediction engine, a news-intelligence product, or an automated investment adviser.

Radar does not claim causal explanations, geopolitical intent, or the reason an observed pattern occurred. It does not turn a correlation into a forecast merely because the correlation is numerically visible.

## External Context Boundary

Market, economic, news, or other external datasets may be added as an optional context layer. Their role is to help distinguish:

- broad external conditions from concept-specific changes
- market-wide attention from series-level movement
- event-window overlap from recurring Radar behavior

External context remains descriptive and isolated from the canonical Radar baseline. It does not automatically enter scoring, gate, kernel, persistence, or promotion logic.

An external dataset earns a place only when it improves interpretation of an original Radar question. Adding more symbols, models, or sources is not progress by itself.

## Expansion Rule

Before adding a new data source or analysis feature, record:

1. The original Radar question it helps answer.
2. The artifact or metric that becomes more informative.
3. The independent or future-data check that can falsify the hypothesis.
4. The stopping condition when the feature adds no durable information.

If a feature only produces more candidates without improving reproducibility, interpretation, or out-of-window validation, keep it out of the mainline system.

## Three-Project Boundary

- `DBAI` defines identity and discovery anchors.
- `concept-markers` publishes concepts and their relational topology.
- `civilization-radar` observes those published structures over time and verifies the resulting evidence.

Guiding statement:

> Radar observes responses around the concept network; it does not claim to explain or predict the world.
