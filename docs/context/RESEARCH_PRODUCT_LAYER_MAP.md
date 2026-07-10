# Research to Product Layer Map

Status snapshot: 2026-03-17

## Purpose

This file explains the three-layer value model used to interpret the current state of:

- `DBAI-Domain-Based-Agent-Identity`
- `concept-markers`
- `civilization-radar`

The model is:

- `research value`
- `bridge layer`
- `product interface`

This is not a canonical ops contract. It is a strategy and positioning note for cross-project planning.

## The Three Layers

### Research Value

This layer contains the hardest-to-replace ideas:

- the problem definition
- the conceptual framework
- the system architecture
- the contribution logic
- the trust and verification model

This is the layer most likely to be legible in research, applications, proposals, or long-form writing.

### Bridge Layer

This layer turns a framework into something executable:

- validators
- receipts
- contracts
- governance workflows
- publishing workflows
- gates
- repeatable analysis or monitoring procedures

This is the layer that makes the project usable, testable, and operational.

### Product Interface

This is the most visible layer:

- dashboards
- reports
- maps
- explorers
- public views
- interactive tools

This is the layer that external users usually see first.

## Repo Mapping

### DBAI-Domain-Based-Agent-Identity

#### Research Value

- domain-based agent identity as a minimal discovery convention
- anchor / manifest / resolver model
- trust boundary between naming, control, and capability
- identity-only core with semantic separation

#### Bridge Layer

- `resolver/resolver-checklist.md`
- manifest publication conventions
- validation logic for anchor consistency and proof
- future manifest checker or onboarding workflow

#### Product Interface

- possible future manifest validator UI
- resolver explorer
- agent identity profile viewer

#### Current Maturity

- strongest layer: `research value`
- second strongest: `bridge layer`
- weakest layer: `product interface`

#### Most Useful Next Strengthening

- strengthen the bridge layer first
- make validation and onboarding more concrete before worrying about a polished public product surface

### concept-markers

#### Research Value

- concept topology
- relational layer
- mirror semantics across `.com`, `.ai`, and `.systems`
- governance framing for semantic infrastructure

#### Bridge Layer

- `domains.json` as canonical inventory
- `networklayer/markers.js` as single source of truth
- audit and generation workflows
- `ops/*locksheet*.md`
- site-copy locking and governance process

#### Product Interface

- concept network explorer
- domain relationship browser
- public relational map
- semantic publishing interface

#### Current Maturity

- strongest layer: `bridge layer`
- second strongest: `research value`
- weakest layer: `product interface`

#### Most Useful Next Strengthening

- finish or stabilize lock and governance work before major runtime materialization
- keep future product surfaces downstream of the lock discipline, not ahead of it

### civilization-radar

#### Research Value

- observation baseline as a trust model
- artifact-first verification
- reproducible monitoring and non-interference rules
- baseline comparability and deterministic receipts

#### Bridge Layer

- collect / acceptance / promote flow
- scheduler receipts
- quality gates
- anomaly and trend checks
- closeout and triage procedures

#### Product Interface

- dashboard
- heat maps
- hotspot views
- weekly or monthly observation reports
- future crisis or anomaly surface

#### Current Maturity

- strongest layer: `bridge layer`
- second strongest: `research value`
- most visible layer: `product interface`

#### Most Useful Next Strengthening

- preserve baseline trust first
- fix operational integrity issues before expanding the public-facing dashboard story

## Why This Model Helps

- It explains why the repos feel more research-like than product-like right now.
- It shows that visible surfaces such as maps and dashboards are not the whole project.
- It gives a cleaner answer to "what is the value here?" without collapsing everything into either academic theory or immediate monetization.
- It helps sequence work:
  - stabilize research logic
  - operationalize the bridge layer
  - then expose product surfaces

## Practical Reading

- `DBAI` currently has the clearest research framing.
- `concept-markers` currently has the strongest governance and publishing bridge layer.
- `civilization-radar` currently has the strongest operational bridge layer and the clearest near-term product surface.

## GPT Notes

- Do not reduce these repos to only their visible UI layer.
- When explaining value, distinguish between deep value and visible value.
- When discussing future monetization, treat the bridge layer as the key transition point between research and product.
