# Three Projects Overview

Status snapshot: 2026-03-17

## Purpose

This file is a cross-project context note for GPT support across three related repositories:

- `concept-markers`
- `civilization-radar`
- `DBAI-Domain-Based-Agent-Identity`

It is a synthesis layer, not a replacement for canonical repo docs.

## Three-Project Map

- `concept-markers`: concept and relational layer
- `civilization-radar`: observation and verification layer
- `DBAI-Domain-Based-Agent-Identity`: identity discovery layer

## Each Project in One Paragraph

### concept-markers

`concept-markers` is a static-only network of concept pages. Its operational center is `domains.json` as canonical inventory and `networklayer/markers.js` as the shared footer and marker source. The repo is closer to a contract-driven content and topology system than a conventional app: there is no backend, database, or runtime service, and verification is driven by generation and audit scripts.

### civilization-radar

`civilization-radar` is an event-driven observation system for cross-series risk propagation. It is currently in `v0.7 Observation Baseline`, which means operational reliability, deterministic verification, and baseline comparability take priority over feature work. The canonical operational contract is defined through `docs/ops`, output semantics, eval rules, and scheduled collect and promote rhythms.

### DBAI-Domain-Based-Agent-Identity

`DBAI-Domain-Based-Agent-Identity` is a specification-oriented repo for a minimal identity discovery convention. It uses domains as durable anchors, agent manifests as discovery documents, and decentralized resolvers as the validation mechanism. It is not a heavy runtime system; it is primarily a conceptual and standards-layer project with a roadmap from `v0.1 current` toward a frozen `v1.0` identity core.

## How They Connect

- `DBAI` defines how a digital actor can be persistently found and anchor itself on the open web.
- `concept-markers` defines how concepts, clusters, and relational structures are published and connected as a reference network.
- `civilization-radar` observes outputs and patterns over time, turning networked inputs into verifiable operational artifacts.

One useful way to think about the stack is:

- identity and discoverability -> `DBAI`
- concepts and topology -> `concept-markers`
- observation and verification -> `civilization-radar`

## Shared Vocabulary

- `anchor`: a durable reference point, especially in `DBAI`
- `artifact`: a generated output treated as a verifiable state record
- `baseline`: a locked comparison reference used to avoid silent drift
- `canonical`: the source of truth inside a repo
- `contract`: a file or rule that defines allowed behavior
- `discoverability`: the ability to find an actor or document consistently
- `relational layer`: the topology that connects concepts or identity domains
- `verification`: read-only checks that confirm state without changing it

## Current Cross-Project Priorities

- Keep GPT support grounded in canonical docs instead of ad hoc chat history.
- Maintain a current-status layer for each repo so time-sensitive state does not get mixed into stable specs.
- Preserve `civilization-radar` baseline trust while closeout is still pending on `2026-03-18`.
- Keep `concept-markers` verification and topology governance understandable to non-authors.
- Keep `DBAI` positioned clearly as a minimal identity discovery convention, not as a full identity stack.

## Current Cross-Project Risks

- Time-scoped notes can be mistaken for permanent truth if GPT reads task logs without a status summary.
- `civilization-radar` still has verified operational risks, but they are intentionally deferred until after closeout.
- `concept-markers` verification is not a perfect release gate yet because strict audit and formatting coverage still have gaps.
- `DBAI` is still an early-stage spec repo, so some roadmap items remain directional rather than fully operational.

## What Is Canonical in Each Repo

### concept-markers

- `README.md`
- `RELATIONAL_LAYER.md`
- `AGENTS.md`
- `ops/governance-layer-map.md`
- `ops/identity-radar-map.md`

### civilization-radar

- `README.md`
- `AGENTS.md`
- `docs/ops/BASELINE.md`
- `docs/ops/RUNBOOK.md`
- `docs/architecture/OUTPUTS.md`
- `docs/metrics/EVAL.md`
- `docs/RADAR_AGENT_CONTRACT_v0.1.md`
- `docs/OBSERVER_CONTRACT_v0.1.md`

### DBAI-Domain-Based-Agent-Identity

- `README.md`
- `ABSTRACT.md`
- `VISION.md`
- `DESIGN_PRINCIPLES.md`
- `OOSITIONING.md`
- `FAQ..md`
- `resolver/resolver-checklist.md`

## GPT Notes

- Use this file as orientation only.
- When repo-specific answers matter, defer to that repo's canonical docs first.
- Treat status files as fresher than evergreen philosophy docs for near-term planning.
