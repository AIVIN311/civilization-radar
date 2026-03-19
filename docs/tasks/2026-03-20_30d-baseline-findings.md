# Task - Baseline Findings under Imperfect System

Date: 2026-03-20  
Window interpreted: 2026-02-17 through 2026-03-18  
Scope: docs-only interpretation memo for the completed 30-day observation window

## Goal

- Interpret the just-closed 30-day window as an observation trace that is useful for engineering judgment now and still reusable later as research framing.
- Make explicit which findings should currently be read as `likely signal`, `likely artifact`, or `uncertain`.
- Preserve the repo's baseline stance: this memo does not upgrade the window into a high-confidence ground-truth dataset.

## Allowed changes

- Docs-only memo under `docs/tasks/`
- Read-only synthesis of:
  - `docs/tasks/2026-02-17_30d-observation-weekly-check.md`
  - `docs/tasks/2026-03-18_observation-baseline-closeout.md`
  - `docs/tasks/2026-03-19_blocking-operational-fixes.md`
  - `docs/context/civilization-radar-current-status.md`

## Do-not-touch list

- No runtime code changes
- No scheduler configuration changes
- No pipeline flow, DB schema, scoring, gate, kernel, or persistence changes
- No observer/product expansion decisions
- No mutation of `output/latest`

## Confidence posture

- `qualitative > quantitative`: this memo is better suited to explaining the shape of the window than to defending exact numeric conclusions.
- `directional > precise`: read the window for direction, stability class, and trust boundaries more than for precise magnitude claims.
- `hypotheses > strong claims`: use this memo to decide what deserves re-check, follow-up, or later study, not to close debate with high-confidence assertions.

## What this 30-day window can support

- `likely signal`: the system sustained a usable observation cadence across the window, with the closeout receipt on `2026-03-18` showing scheduler success, fresh live snapshot status, and `output/latest/reports/eval_quality.json` still reporting `ok = true`.
- `likely signal`: the repo can support operational questions about continuity, freshness, and promote health. The weekly-check and closeout docs are strong enough to support claims such as "the monitored ops loop remained functioning under constrained conditions."
- `likely signal`: the window is suitable for identifying which artifact contracts mattered most in practice. Batch A on `2026-03-19` directly addressed three contract-level weaknesses revealed by the window, which means the period was informative about system reliability boundaries.
- `uncertain`: the window can support qualitative pattern review for follow-up prioritization, but only when those patterns are treated as candidates for re-check rather than settled empirical conclusions.

## What it cannot support

- This window should not be treated as a high-confidence quantitative dataset for strong claims about real-world event prevalence, exact comparative magnitudes, or downstream forecasting quality.
- It cannot support "ground truth" language. The observation path was intentionally baseline-safe and operationally constrained, not designed as a full validation study.
- It cannot cleanly separate environment effects from system effects for every derived output. During part of the window, some render and metadata behaviors were later shown to be artifact-sensitive.
- It cannot justify changing scoring, gate, kernel, persistence, or schema logic. The evidence here is interpretive and operational, not a basis for core model rewrites.

## Known system bias sources during the window

- `likely artifact`: scheduler execution remained `Interactive only` / `InteractiveToken`, so the window demonstrates operator-present reliability more than headless reliability.
- `likely artifact`: promoted freshness is weekly by design for `output/latest`, which means the canonical latest artifacts lag within-week runtime collection and should not be read as day-by-day final state snapshots.
- `likely artifact`: before Batch A, promoted `eval_quality.json` was not fully self-contained because it embedded an acceptance-run DB path rather than the canonical `output/latest` DB path.
- `likely artifact`: before Batch A, explanatory kernel selection could be backdated by stale artifact timestamps, which weakens confidence in exact timing interpretation for some pre-fix derived views.
- `uncertain`: render behavior was required to be non-fatal, but the need for the `2026-03-19` fallback fix means any pre-fix absence or oddity in explanatory surfaces should be treated cautiously unless corroborated elsewhere.

## Stable signals worth attention

- `likely signal`: the operating rhythm itself held. The fixed cadence remained Mon-Thu collect, Fri promote, and daily self-gated month-end checks, with the `2026-03-18` closeout recording `Last Result = 0` for all three scheduled tasks.
- `likely signal`: live snapshot continuity remained credible within the window. The closeout recorded fresh `output/live/live_snapshot_status.json` with `max_date = 2026-03-18`, `today_unique_domains = 67`, and `bad_json_lines = 0`.
- `likely signal`: acceptance and promoted quality gate health remained intact across the closeout boundary. The canonical latest gate continued to report `ok = true`, which supports using the window as a reliability baseline for ops checks.
- `likely signal`: the window successfully surfaced contract-level weaknesses without requiring baseline-sensitive algorithm changes. That is useful both operationally and as a research note about where interpretation pressure concentrates in an artifact-first system.

## Unstable or suspicious patterns

- `likely artifact`: any apparent precision in pre-Batch-A kernel timing should be treated cautiously because stale artifact timestamps could backdate explanatory output.
- `likely artifact`: any inference that relied on the pre-Batch-A promoted `eval_quality.json` DB path as a canonical provenance indicator is weak; the receipt contract was corrected only on `2026-03-19`.
- `uncertain`: dashboard absences, degraded explanatory sections, or schema-missing behavior observed before the non-fatal render fix are not strong evidence of underlying state absence on their own.
- `uncertain`: within-week comparisons between fresh live collection state and older promoted `output/latest` artifacts may reflect cadence differences more than substantive system change.
- `likely signal`: the remaining deferred ops topic, headless scheduler hardening, was not exposed as a scoring or data-integrity defect during the window, but it remains a reliability gap because the observation trace did not prove unattended execution robustness.

## Batch A before/after interpretation notes

- Before Batch A (`2026-03-19`), read the window as operationally informative but contract-imperfect. Use pre-fix outputs mainly to answer "what looked stable enough to preserve?" rather than "what exact quantitative conclusion should we publish?"
- Before Batch A, label affected interpretation areas as:
  - `likely artifact`: promoted `eval_quality.json` provenance
  - `likely artifact`: exact kernel timing when stale artifact timestamps were present
  - `uncertain`: render omissions tied to missing DB/schema cases
- After Batch A, the system is easier to interpret because:
  - render fallback is non-fatal
  - promoted `eval_quality.json` is canonical to `output/latest\radar.db`
  - kernel timestamp alignment no longer backdates explanatory output
- After Batch A, confidence improves for future observation windows, but Batch A does not retroactively convert the earlier 30-day trace into a clean final-results dataset.
- Practical reading rule:
  - if a finding survives both the closeout evidence and the post-Batch-A contract fixes, treat it as stronger `likely signal`
  - if a finding depends on pre-fix provenance or timing details, keep it as `likely artifact` or `uncertain` until rechecked on post-Batch-A outputs

## Verification steps

1. Confirm the memo reads as an interpretation artifact, not a final-results claim.
2. Confirm the memo explicitly states the dataset is not for high-confidence quantitative conclusions.
3. Confirm the memo separates stable signals, suspicious patterns, and Batch A re-check guidance.
4. Confirm this file is the only intended new tracked file in its commit.

## Results / notes

- This memo records the 30-day window as a constrained but still useful observation trace.
- The intended reading posture is:
  - use `likely signal` for operationally corroborated continuity and contract observations
  - use `likely artifact` for findings exposed as pre-fix contract weaknesses
  - use `uncertain` for patterns that require post-Batch-A re-check before stronger claims
- No runtime behavior, scheduler state, or canonical outputs were changed by this memo.

## Follow-ups

- Use this memo as the interpretation layer for any later research-style summary of the Observation Baseline window.
- Re-check any pre-Batch-A suspicious pattern against post-`2026-03-19` artifacts before using it in stronger comparative analysis.
- Keep the first `v0.7.1 ops` implementation slice scoped to scheduler hardening only, separate from this interpretation memo.
