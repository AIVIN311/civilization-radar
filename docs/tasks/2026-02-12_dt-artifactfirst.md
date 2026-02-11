# TASK — DT Artifact-first Render Adjustment

Date: 2026-02-12
Scope: Render ΔT provider adjustment
Mode: Observation-safe

---

## Goal

Switch render_dashboard_v02.py ΔT source to:

1. Artifact-first (PR-7 class artifact)
2. Fallback → PR-8 DB minimal provider

Without modifying scoring/gate/kernel/pipeline logic.

---

## Allowed Changes

- render_dashboard_v02.py ΔT provider
- Derived render metadata output
- Safe fallback implementation

---

## DO NOT TOUCH

- persistence_v1.py compute_tag_persistence
- persistence_v1.py classify_ers
- persistence_v1.py compute_event_kernel
- metrics_v02.W routing path
- strength / push / gate paths
- DB schema
- pipeline main flow

Any artifact read error must fallback safely and NOT crash render.

---

# Verification — Phase 1

## Task Scheduler Audit (record only)

| Task Name | Logon Mode | LogonType | WakeToRun | Notes |
|-----------|------------|-----------|-----------|-------|
|           |            |           |           |       |

(No modifications allowed in this phase.)

---

# Verification — Phase 2

## Pipeline Smoke Test

Steps:

1. Run collect
2. Run promote
3. Check git status
4. Run render

| Check | Result | Notes |
|-------|--------|-------|
| git status clean |        |       |
| render no crash |        |       |
| ΔT artifact read |        |       |
| fallback works |        |       |

---

## Outcome

- Baseline preserved: YES / NO
- Drift detected: YES / NO
- Follow-up required:
