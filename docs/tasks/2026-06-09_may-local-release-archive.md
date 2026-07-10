# 2026-06-09 May Local Release Archive

## Goal

- Preserve the verifiable 2026-05 closeout evidence as a local recovered archive.
- Keep the distinction between local recovered observation and remote tag-pushed release explicit.
- Avoid rerunning pipeline or changing scoring.
- After explicit operator approval, create and push only `radar-release-202605`.

## Allowed Changes

- Create `output/releases/2026-05/` as a generated local archive.
- Copy existing May closeout receipts and documentation into the archive.
- Add May-only and through-May snapshot integrity artifacts generated from `input/snapshots.jsonl`.
- Add this task note.
- After explicit operator approval, create and push annotated tag `radar-release-202605`.

## Do-Not-Touch List

- `persistence_v1.py`
- `compute_tag_persistence`
- `classify_ers`
- `compute_event_kernel`
- `metrics_v02.W` path assumptions
- strength / push / gate paths
- DB schema
- pipeline main flow
- secrets or token rotation
- any remote tag other than the explicitly approved `radar-release-202605`

## Verification Steps

- Confirm `output/releases/` was missing before the archive step.
- Copy the natural failed and recovered May month-end receipts.
- Verify May snapshot coverage from `input/snapshots.jsonl`.
- Verify the through-May snapshot archive hash matches the recovered May receipt `input_sha256`.
- Verify `radar-release-202605` is not present locally or remotely before creating it.
- After explicit operator approval, create and push `radar-release-202605`.
- Verify the remote tag exists and points to the expected target commit.
- Confirm no tracked source files were changed except this task note.

## Results / Notes

- Created local archive: `output/releases/2026-05/`.
- Archived receipts:
  - `reports/month_end_20260531T110004Z.natural_failed.json`
  - `reports/month_end_20260531T110500Z.recovered_success_no_push.json`
- Archived docs:
  - `docs/2026-05-civilization-radar-monthly-observation-memo-v0.1.md`
  - `docs/2026-06-01_may-closeout-recovery.md`
- Archived snapshot files:
  - `input/snapshots_2026-05.jsonl`
  - `input/snapshots_through_2026-05-31.jsonl`
- Integrity manifest:
  - `manifest.json`
  - `integrity/may_snapshot_integrity.json`
- May coverage:
  - rows: `2077`
  - dates: `31`
  - expected domains per day: `67`
  - dates not at 67 domains: `[]`
  - duplicate May `(date, domain)`: `0`
  - bad JSON lines seen in current input scan: `0`
- May totals:
  - `dns_total`: `57097219`
  - `cf_served`: `12197406`
  - `origin_served`: `44899813`
  - `edge_origin_ratio`: `0.272`
- Hash proof:
  - recovered receipt `input_sha256`: `e78f93b874b587e3cb4ee78e61ea75853c07f8f46098b7e4dd183ac5d73e7a61`
  - archive `input/snapshots_through_2026-05-31.jsonl` SHA256: `e78f93b874b587e3cb4ee78e61ea75853c07f8f46098b7e4dd183ac5d73e7a61`
  - match: `true`
- Initial tag status before explicit seal approval:
  - local `radar-release-202605`: not found
  - remote `radar-release-202605`: not found
- Later tag seal after explicit operator approval:
  - local `radar-release-202605`: created
  - remote `radar-release-202605`: pushed
  - tag object: `4f0a648bb2478a7f0c55b32fd1c457ec42528620`
  - target commit: `6dafd0fb2505338715baeedf6514229914eff27f`
  - target commit subject: `docs(observations): add May closeout memo`
  - remote ref: `refs/tags/radar-release-202605`
- Boundary:
  - This archive supports `recovered May observation archive with later remote tag seal`.
  - It does not support claiming the original natural month-end run pushed the tag.
  - The recovered receipt remains `success_no_push`; the remote tag was created and pushed later after explicit operator approval.

## Follow-Ups

- Consider adding a durable monthly archive step to `ops/month_end_release.ps1` in a future task, with a safe fallback and verification.
