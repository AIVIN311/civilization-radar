# v0.7 — Observation Baseline

v0.7 標誌著 Civilization Radar 進入「觀測模式」。

在此階段，系統的首要目標不是擴張功能、優化分數或追求指標成長，而是確立一個穩定、可重現、可驗證的觀測基準。所有 pipeline、artifact 與 render 輸出，都必須在不改變核心計算邏輯的前提下，保持一致性與可追溯性。

此版本凍結核心演算法（persistence / kernel / gate / scoring）路徑。任何實驗性改動，必須以 artifact-first 的方式引入，並具備安全 fallback。render 層可調整，資料來源可優化，但不得污染 baseline 或改寫既有數學結構。

在 Observation Baseline 階段：
- 正確性優先於速度
- 穩定性優先於創新
- 可解釋性優先於複雜度

所有輸出皆應可回溯至明確 artifact。
任何例外情況不得中斷主流程。

這不是停滯，而是壓縮。
這不是保守，而是建立未來擴張的參考點。

v0.7 是一個基準版本。
未來所有變動，都必須能與它比較。

---

## 1. Baseline Invariants

Core principle:
- Deterministic pipeline
- Reproducible outputs
- Non-interference preference
- Stability over feature expansion

---

## 2. Blocking Definition

The following are blocking:
- Any change that alters scoring logic
- Any change that alters gate behavior
- Any DB schema modification
- Any change that breaks output comparability

Non-blocking:
- Documentation updates
- Render-only metadata additions (non-breaking)
- Fallback logic that preserves baseline behavior

---

## 3. Guardrails (Permanent Invariants)

Unless explicitly requested:
- Do not modify `persistence_v1.py`:
  - `compute_tag_persistence`
  - `classify_ers`
  - `compute_event_kernel`
- Do not modify `metrics_v02.W` path assumptions
- Do not modify strength/push/gate routing
- Do not modify DB schema or pipeline flow
- Render must never crash due to artifact read failure

---

## 4. Execution Scope Rules

### Weekly Operations
- Snapshots: collected automatically (no manual action required)
- Promotion to `output/latest`: once per week (Friday)

### Monthly Operations
- Run full pipeline once
- Produce release tag
- Archive monthly artifacts

---

## 5. When Full Pipeline Is Allowed

Full pipeline execution is allowed only when:
1. Monthly scheduled run
2. Acceptance promotion fails
3. Schema / data structure changes
4. Explicit manual approval

---

## 6. Output Directory Contract

Stable paths:
- `output/latest/`
- `output/releases/`
- `output/archive/`

Agents must not change directory structure without approval.
