# RUNBOOK

Operational procedures for Civilization Radar.

Canonical rule: snapshot, acceptance, and promote must use the single entry commands below.

---

## 1. Snapshot Collection

Single entry command:
`powershell -ExecutionPolicy Bypass -File .\ops\collect_snapshots_weekday.ps1`

Expected:
- Appends runtime snapshots via scheduled collection logic
- Does not modify Git-tracked source files

Verify:
- `git status --short` has no snapshot pollution

---

## 2. Acceptance

Single entry command:
`python scripts/run_acceptance_latest.py`

Expected:
- Deterministic metrics
- No schema drift
- No baseline drift
- `output/latest/reports/eval_quality.json` exists and reports `ok = true`

---

## 3. Promote

Single entry command:
`powershell -ExecutionPolicy Bypass -File .\ops\promote_latest.ps1`

Expected:
- Refreshes `output/latest` artifacts from accepted outputs
- Keeps `latest` as stable operational reference

---

## 4. Smoke Test

After collect + acceptance + promote:
- `git status --short` clean (no snapshot pollution)
- `output/latest/reports/eval_quality.json` exists and `ok = true`
- `output/latest/radar.db` refreshed
- Render path remains non-fatal when artifacts are missing

If failure:
- Abort feature work
- Fix operational root cause first
