# OUTPUTS — Artifact Semantics

This project distinguishes between:

- Working artifacts
- Immutable reference artifacts

---

## output/latest

Meaning:
- Canonical latest accepted state
- Comparable across time
- Must not be manually edited

Properties:
- Immutable after promotion
- Only overwritten by promote step
- Baseline reference for evaluation

---

## Artifact-first rule

When rendering:

1. Prefer reading from artifact (output/latest or PR artifacts)
2. If artifact missing → safe fallback to DB minimal provider
3. Fallback must not alter scoring/gate behavior

Render must never crash.
