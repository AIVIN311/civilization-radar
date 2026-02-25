# OBSERVER_CONTRACT_v0.1

## 1. Purpose
Radar Observer v0.1 exists solely to detect structural health and statistical deviations within the existing data baseline. 
It MUST NOT influence ingestion, scheduling, promotion, or interpretation. It operates strictly as a read-only detection layer.

## 2. Immutable Operational Boundaries
### Observer v0.1 MUST:
- Operate STRICTLY in read-only mode.
- Read only the following sources:
  - `radar.db` (via read-only connection).
  - `snapshots.jsonl`.
  - Receipt markers / file existence indicators.
- Produce ONLY the following outputs:
  - `stdout` summary.
  - Optional JSON reports (e.g., `observer_reports/YYYY-MM-DD.json`).

### Observer v0.1 MUST NOT:
- Write to, modify, or lock `radar.db`.
- Modify `output/latest` or any historical data states.
- Trigger ingestion workflows.
- Trigger promotion/deployment workflows.
- Modify schedules (e.g., cron jobs).
- Make external network requests.
- Call any external models (LLMs/APIs) during runtime.
- Generate causal explanations, narratives, or geopolitical inferences.

*Violation of any of the above constitutes a severe design error.*

## 3. Strict Output Structure
Observer output is strictly limited to three layers. It MUST NOT exceed these layers.

### Layer 0 – Numerical Facts
- `counts`, `ratios`, `deltas`, `top-N changes`.

### Layer 1 – Taxonomy (Signal Classification)
- **ALERT**: Ingestion continuity failure only (e.g., Data continuity failure, Missing batch, Schema mismatch, Pipeline interruption).
- **WARN**: Statistical deviation beyond defined threshold (e.g., >3σ or >200% single-window deviation).
- **TREND**: N consecutive directional changes across multiple windows. *(Note: Country-share TREND must never escalate to ALERT unless ingestion integrity is impacted.)*

### Layer 2 – Human Prompts (Optional, No Answers)
Must be strictly instructional and devoid of causal statements.
- Allowed phrases: "Requires manual verification", "Recommend manual review".

## 4. Language Constraints
The Observer may format data for readability but MUST NOT claim causality.

- **PROHIBITED CONSTRUCTS**: "because", "therefore", "indicates that", "this means", "clearly", "targeting", "attack", "manipulation".
- **PERMITTED VOCABULARY**: "observed", "delta", "ratio", "count", "window", "sample", "share".

## 5. Evolution Roadmap
The Observer's capabilities are strictly version-locked. Skipping stages is PROHIBITED.
- **v0.1** – Detection only (Current).
- **v0.2** – Descriptive sentences (non-causal).
- **v0.3** – Operational suggestions (engineering scope only).
- **v0.4** – Human-confirmed action triggers.