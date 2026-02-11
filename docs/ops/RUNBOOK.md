# RUNBOOK

Operational procedures for Civilization Radar.

---

## 1. Snapshot Collection

Command:
python collect_snapshots.py

Expected:
- Writes to output/snapshots/
- Does not modify git-tracked state

Verify:
git status should be clean

---

## 2. Acceptance

Command:
python run_acceptance_latest.py

Expected:
- Deterministic metrics
- No schema drift
- No baseline drift

---

## 3. Promote

Command:
python promote_latest.py

Expected:
- Copies to output/latest
- latest must be immutable reference

---

## 4. Smoke Test

After collect + promote:

- git status clean
- render_dashboard_v02.py executes without crash
- No snapshot pollution

If failure:
- Abort feature work
- Fix infra first
