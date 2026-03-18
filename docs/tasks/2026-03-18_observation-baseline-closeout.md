# Task - Observation Baseline Closeout

Date: 2026-03-18  
Scope: read-only verification and documentation only

## Goal

- Formally close the 30-day Observation Baseline window on `2026-03-18`.
- Capture scheduler, data freshness, acceptance, and `output/latest` receipt state without changing runtime behavior.
- Record known residual risks separately from any later repair or implementation batch.

## Allowed changes

- Docs-only updates under `docs/tasks/`
- Read-only inspection of:
  - Windows Task Scheduler task status
  - `output/live/live_snapshot_status.json`
  - newest `output/reports/acceptance_latest_*.json`
  - `output/latest/reports/eval_quality.json`
  - `output/latest/radar.db`
  - `git status --short`

## Do-not-touch list

- No repair actions in this batch
- No manual full pipeline run
- No changes to pipeline flow, DB schema, scoring, kernel, persistence, or observer scope
- `src/persistence_v1.py` algorithms:
  - `compute_tag_persistence`
  - `classify_ers`
  - `compute_event_kernel`
- `metrics_v02.W` path assumptions
- strength / push / gate routing
- any mutation of `output/latest`

## Verification steps

1. Query scheduler task state:

```powershell
schtasks /Query /TN "CivilizationRadar-WeekdaySnapshots" /V /FO LIST
schtasks /Query /TN "CivilizationRadar-FridayPromote" /V /FO LIST
schtasks /Query /TN "CivilizationRadar-MonthEndPipelineTag" /V /FO LIST
```

2. Read runtime freshness receipt:

```powershell
Get-Content .\output\live\live_snapshot_status.json
```

3. Inspect latest acceptance receipt and latest quality gate:

```powershell
Get-ChildItem .\output\reports\acceptance_latest_*.json |
  Sort-Object LastWriteTimeUtc -Descending |
  Select-Object -First 1 FullName, LastWriteTimeUtc, Length

Get-Content .\output\latest\reports\eval_quality.json
```

4. Inspect canonical latest DB freshness:

```powershell
Get-Item .\output\latest\radar.db | Select-Object FullName, LastWriteTimeUtc, Length
```

5. Inspect repo cleanliness:

```powershell
git status --short
```

Pass criterion:
- local operator noise (for example `.codex/`) may be ignored
- no tracked modifications may be introduced by closeout verification itself

6. Record final `2026-03-18` receipt in this file.
   If any check fails, record it as an observation only and defer repair into post-closeout triage.

## Results / notes

- Preparation note:
  - this file was created on `2026-03-17`
  - final closeout receipt must be completed on `2026-03-18`
- Pre-closeout checkpoint captured at `2026-03-17T19:45:54.8881975+08:00`
- Scheduler health snapshot:
  - `CivilizationRadar-WeekdaySnapshots`: `Last Run Time = 2026/3/17 18:00`, `Last Result = 0`, `Next Run Time = 2026/3/18 18:00`, `Logon Mode = Interactive only`
  - `CivilizationRadar-FridayPromote`: `Last Run Time = 2026/3/13 18:00`, `Last Result = 0`, `Next Run Time = 2026/3/20 18:00`, `Logon Mode = Interactive only`
  - `CivilizationRadar-MonthEndPipelineTag`: `Last Run Time = 2026/3/17 19:00:01`, `Last Result = 0`, `Next Run Time = 2026/3/18 19:00`, `Logon Mode = Interactive only`
- Runtime freshness snapshot from `output/live/live_snapshot_status.json`:
  - `generated_utc = 2026-03-17T10:01:19.865727+00:00`
  - `max_date = 2026-03-17`
  - `today_unique_domains = 67`
  - `bad_json_lines = 0`
- Latest acceptance receipt before closeout:
  - `output/reports/acceptance_latest_20260313T100004Z.json`
  - `LastWriteTimeUtc = 2026-03-13T10:00:23.7660901Z`
- Latest promoted gate snapshot before closeout:
  - `output/latest/reports/eval_quality.json`
  - `LastWriteTimeUtc = 2026-03-13T10:00:08.4674539Z`
  - `ok = true`
  - `db_path = C:\dev\civilization-radar\output\acceptance_v07\run_tw_a\runs\20260313T100005Z\radar.db`
- Latest promoted DB snapshot before closeout:
  - `output/latest/radar.db`
  - `LastWriteTimeUtc = 2026-03-13T10:00:07.7971015Z`
- Repo status before closeout:
  - `git status --short` returned `?? .codex/` only
  - treat `.codex/` as local operator noise, not closeout-generated tracked modification
- Stop-point check for `2026-03-17`:
  - working tree remained limited to the existing docs-only scaffold plus pre-existing local operator noise such as `.codex/`
  - no new code / config / runtime mutations were introduced in the stop-point batch
- Pre-closeout observation snapshot captured at `2026-03-18T16:54:09.3441109+08:00`
- `2026-03-18` pre-closeout scheduler snapshot:
  - `CivilizationRadar-WeekdaySnapshots`: `Status = Ready`, `Scheduled Task State = Enabled`, `Last Run Time = 2026/3/17 18:00`, `Next Run Time = 2026/3/18 18:00`, `Last Result = 0`, `Logon Mode = Interactive only`
  - `CivilizationRadar-FridayPromote`: `Status = Ready`, `Scheduled Task State = Enabled`, `Last Run Time = 2026/3/13 18:00`, `Next Run Time = 2026/3/20 18:00`, `Last Result = 0`, `Logon Mode = Interactive only`
  - `CivilizationRadar-MonthEndPipelineTag`: `Status = Ready`, `Scheduled Task State = Enabled`, `Last Run Time = 2026/3/17 19:00:01`, `Next Run Time = 2026/3/18 19:00`, `Last Result = 0`, `Logon Mode = Interactive only`
- `2026-03-18` pre-closeout runtime freshness:
  - `generated_utc = 2026-03-17T10:01:19.865727+00:00`
  - `max_date = 2026-03-17`
  - `today_unique_domains = 67`
  - `bad_json_lines = 0`
  - `max_date = 2026-03-17` is acceptable in this snapshot because the `2026-03-18 18:00 +08:00` weekday scheduler window had not yet run
- `2026-03-18` pre-closeout acceptance receipt:
  - newest file `output/reports/acceptance_latest_20260313T100004Z.json`
  - `LastWriteTimeUtc = 2026-03-13T10:00:23Z`
  - Wednesday closeout continues to anchor freshness to the last Friday promote until `2026-03-20`
- `2026-03-18` pre-closeout promoted gate snapshot:
  - `output/latest/reports/eval_quality.json` parsed successfully
  - `ok = true`
  - `db_path = C:\dev\civilization-radar\output\acceptance_v07\run_tw_a\runs\20260313T100005Z\radar.db`
- `2026-03-18` pre-closeout canonical artifact snapshot:
  - `output/latest/radar.db`: `LastWriteTimeUtc = 2026-03-13T10:00:07Z`, `Length = 167936`
  - `output/latest/dashboard_v04.html`: `LastWriteTimeUtc = 2026-03-13T10:00:07Z`, `Length = 26357`
- `2026-03-18` pre-closeout dashboard smoke check:
  - PASS: local dashboard loaded with title `Civilization Radar v0.4`
  - main UI sections were present: domain table, event list, chain list
  - only console error was missing `favicon.ico`, treated as non-fatal
- `2026-03-18` pre-closeout repo status:
  - `git status --short` returned:
    - `M docs/context/THREE_PROJECTS_OVERVIEW.md`
    - `?? .codex/`
    - `?? docs/context/RESEARCH_PRODUCT_LAYER_MAP.md`
  - treat those entries as expected local baseline state, not runtime pollution
  - no extra tracked/runtime drift was observed before the final receipt window
- Final closeout receipt completed after the post-`2026-03-18 19:05 +08:00` refresh at `2026-03-18T19:18:20.8494629+08:00`

### Final closeout receipt (completed on 2026-03-18)

- Verification time: `2026-03-18T19:18:20.8494629+08:00`
- `CivilizationRadar-WeekdaySnapshots` result: `Status = Ready; Scheduled Task State = Enabled; Last Run Time = 2026/3/18 18:00; Next Run Time = 2026/3/19 18:00; Last Result = 0; Logon Mode = Interactive only`
- `CivilizationRadar-FridayPromote` result: `Status = Ready; Scheduled Task State = Enabled; Last Run Time = 2026/3/13 18:00; Next Run Time = 2026/3/20 18:00; Last Result = 0; Logon Mode = Interactive only`
- `CivilizationRadar-MonthEndPipelineTag` result: `Status = Ready; Scheduled Task State = Enabled; Last Run Time = 2026/3/18 19:00:01; Next Run Time = 2026/3/19 19:00; Last Result = 0; Logon Mode = Interactive only`
- `output/live/live_snapshot_status.json` fresh `max_date`: `generated_utc = 2026-03-18T10:01:29.075369+00:00; max_date = 2026-03-18; today_unique_domains = 67; bad_json_lines = 0`
- newest `acceptance_latest_*.json`: `output/reports/acceptance_latest_20260313T100004Z.json; LastWriteTimeUtc = 2026-03-13T10:00:23Z`
- `output/latest/reports/eval_quality.json` `ok`: `true; db_path = C:\dev\civilization-radar\output\acceptance_v07\run_tw_a\runs\20260313T100005Z\radar.db`
- `output/latest/radar.db` freshness: `LastWriteTimeUtc = 2026-03-13T10:00:07Z; Length = 167936; unchanged from the last Friday promote and still consistent on Wednesday 2026-03-18`
- `git status --short` result: `M docs/context/THREE_PROJECTS_OVERVIEW.md; M docs/tasks/2026-03-18_observation-baseline-closeout.md; ?? .codex/; ?? docs/context/RESEARCH_PRODUCT_LAYER_MAP.md`
- Closeout result: PASS

- Final closeout dashboard note: `Phase 1 dashboard smoke PASS remains valid because output/latest/dashboard_v04.html remained unchanged at LastWriteTimeUtc = 2026-03-13T10:00:07Z and Length = 26357.`

## Known residual risks

- `render non-fatal fallback broken`
- `promoted eval_quality.json not self-contained`
- `artifact-first timestamp can backdate kernel output`
- These risks are recorded for post-closeout triage only.
- No risk in this section is fixed in the closeout batch.

## Follow-ups

- Observation Baseline closeout completed on `2026-03-18` with result `PASS`.
- Open `A. blocking operational fixes` as the next implementation batch.
- Keep `B. v0.7.1 ops` deferred until after batch A.
- Use `docs/tasks/2026-03-18_post-closeout-triage.md` only after closeout receipt has been completed.
