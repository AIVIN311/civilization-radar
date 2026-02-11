# 2026-02-12 Route Lock

## Goal
Lock documentation onboarding to a single canonical route and close legacy ops-doc routes using move + tombstone.

## Allowed changes
- Docs-only updates in `README.md`, `README`, `AGENTS.md`, `docs/**`, `ops/*.md` tombstones.
- Canonical ops docs move to `docs/ops/*`.
- Navigation and path contract updates to `docs/ops/*` and `docs/tasks/*`.

## Do-not-touch list
- No scoring/gate/kernel/persistence logic changes.
- No DB schema changes.
- No pipeline flow rewiring.
- No runtime command behavior changes.

## Verification steps
1. Ran route-lock residual scans across `README.md`, `README`, `AGENTS.md`, `docs`, and `ops`.
2. Ran legacy command and legacy task-path scan in docs entry files.
3. Checked single-entry command paths exist.
4. Checked change scope via `git status --short`.

## Results / notes
- Route-lock scans show no `ops/...` legacy doc paths in navigation entry files.
- Legacy `.md` files under `ops/` are tombstones only and redirect to `docs/ops/*`.
- Single-entry command paths all exist:
  - `ops/collect_snapshots_weekday.ps1` = `True`
  - `ops/promote_latest.ps1` = `True`
  - `scripts/run_acceptance_latest.py` = `True`
- Changed files are docs-only.

## Follow-ups
- Optional: replace static latest-task links with a stable pointer doc if frequent task-log churn becomes noisy.
「驗收三連擊」

你現在進入的是：把“已完成”變成“可被未來反覆信任”。

1) 檢查 tombstone 是否真的存在（避免外部連結斷）
Test-Path "ops/OBSERVATION_BASELINE.md"
Test-Path "ops/weekly_rhythm.md"
Test-Path "ops/radar_acceptance_protocol.md"
Test-Path "ops/radar_non_interference_rules.md"
Test-Path "ops/radar_agent_task_template.md"


預期：都 True

2) 檢查 canonical docs 是否存在
Test-Path "docs/ops/BASELINE.md"
Test-Path "docs/ops/RUNBOOK.md"
Test-Path "docs/ops/weekly_rhythm.md"
Test-Path "docs/ops/radar_acceptance_protocol.md"
Test-Path "docs/ops/radar_non_interference_rules.md"
Test-Path "docs/ops/radar_agent_task_template.md"


預期：都 True

3) 只做「文件範圍」的 git 檢查
git status --short


你要看到的理想畫面是：
只有 README/AGENTS/docs/ops/docs/tasks 這些文件變更；沒有任何 .py / .js / workflow。