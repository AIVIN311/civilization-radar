# EVAL — Quality & Gate Semantics

Defines rules for eval_quality.json.

---

## 1. Quality File

eval_quality.json must include:

- timestamp
- metrics summary
- gate result
- drift indicators (if any)

---

## 2. Gate Semantics

Gate must be deterministic.

Gate must NOT:
- Depend on external mutable state
- Depend on UI-only metadata
- Depend on artifact fallback behavior

---

## 3. Non-negotiable

Changes to:
- scoring
- kernel
- persistence logic
- gate thresholds

Require explicit baseline version bump.
