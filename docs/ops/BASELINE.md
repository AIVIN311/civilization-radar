# BASELINE — Observation Mode

This project operates in **Observation Baseline Mode**.

Core principle:
- Deterministic pipeline
- Reproducible outputs
- Non-interference preference
- Stability over feature expansion

---

## 1. Rhythm

Weekly:
- Snapshot collection (scheduled)
- Promote latest (after acceptance)

Monthly:
- Full pipeline run
- Baseline validation

---

## 2. Blocking Definition

The following are blocking:

- Any change that alters scoring logic
- Any change that alters gate behavior
- Any DB schema modification
- Any change that breaks output comparability

Non-blocking:
- Documentation updates
- Render-only metadata additions (non-breaking)
- Fallback logic that preserves baseline behavior

---

## 3. Guardrails (Permanent Invariants)

Unless explicitly requested:

- Do not modify persistence_v1.py:
  - compute_tag_persistence
  - classify_ers
  - compute_event_kernel
- Do not modify metrics_v02.W path assumptions
- Do not modify strength/push/gate routing
- Do not modify DB schema or pipeline flow
- Render must never crash due to artifact read failure
