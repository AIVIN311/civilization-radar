# RUNBOOK

Operational procedures for Civilization Radar.

Canonical rule: snapshot, acceptance, and promote must use the single entry commands below.

---

## 1. Snapshot Collection

Single entry command:
`powershell -ExecutionPolicy Bypass -File .\ops\collect_snapshots_weekday.ps1`

Expected:
- Appends runtime snapshots via scheduled collection logic
- Writes live receipt artifacts:
  - `output/live/live_snapshot_status.json`
  - `output/live/latest_day_domains.txt`
- Does not modify Git-tracked source files

Verify:
- `git status --short` has no snapshot pollution
- `Get-Content .\output\live\live_snapshot_status.json` is readable
- `max_date` and `today_unique_domains` are present in receipt JSON

---

## 1.0 Date Bucket Resolution (v0.7)

Receipt `max_date` is resolved as:

1. If `ts` exists, bucket = UTC date(`ts`)
2. Else, bucket = `row["date"]`

Notes:
- `ts` is optional in v0.7 ingestion.
- Receipt remains forward-compatible when `ts` starts appearing in runtime rows.
- `dups_date_domain_estimate` is intentionally `null` in v0.7.
  This field is reserved for future expansion and is not estimated now to avoid false-positive duplicate signals.

---

## 1.1 Scheduler Diagnostics (Collect Failure)

If `CivilizationRadar-WeekdaySnapshots` reports `Last Result != 0`:

1. Query task status:
   - `schtasks /Query /TN "CivilizationRadar-WeekdaySnapshots" /V /FO LIST`
2. Enable Task Scheduler operational log (requires elevated shell):
   - `wevtutil set-log Microsoft-Windows-TaskScheduler/Operational /enabled:true`
3. Verify log status:
   - `Get-WinEvent -ListLog 'Microsoft-Windows-TaskScheduler/Operational'`
4. Re-run collect task once and inspect related events:
   - `schtasks /Run /TN "CivilizationRadar-WeekdaySnapshots"`
   - `Get-WinEvent -LogName 'Microsoft-Windows-TaskScheduler/Operational' -MaxEvents 200`

Expected:
- Collect stdout includes retry/progress lines when transient upstream errors occur.
- Task event log records the run outcome and exit status.

---

## 2. Acceptance

Single entry command:
`python scripts/run_acceptance_latest.py`

Mode switches:
- default: v0.7 acceptance (CI-aligned fast mode, includes `--skip-v04-hash`)
- full v0.7: `python scripts/run_acceptance_latest.py --full-v07`
- legacy fallback: `python scripts/run_acceptance_latest.py --legacy-v04`

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
