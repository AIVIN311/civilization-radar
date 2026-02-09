# Civilization Radar — Observation Baseline

## Purpose
This repository operates primarily as a long-term observation instrument.
Stability and continuity are prioritized over feature expansion.

---

## Execution Scope Rules

### Weekly Operations
- Snapshots: collected automatically (no manual action required)
- Promotion to `output/latest`: once per week (Friday)

### Monthly Operations
- Run full pipeline once
- Produce release tag
- Archive monthly artifacts

---

## When Full Pipeline Is Allowed
Full pipeline execution is allowed only when:
1. Monthly scheduled run
2. Acceptance promotion fails
3. Schema / data structure changes
4. Explicit manual approval

---

## PR Rules
Agents may open PR only when:
- CI / acceptance failure detected
- Blocking issue identified
- Explicit instruction given

Non-functional refactors are discouraged during observation period.

---

## Blocking Definition
Blocking = prevents:
- snapshot ingestion
- acceptance run
- promotion to `output/latest`
- dashboard generation

All other issues are non-blocking.

---

## Output Directory Contract
Stable paths:
- output/latest/
- output/releases/
- output/archive/

Agents must not change directory structure without approval.

---

## Observation Mode Principle
During baseline observation:
- prefer promotion over recomputation
- avoid unnecessary pipeline runs
- maintain deterministic outputs
