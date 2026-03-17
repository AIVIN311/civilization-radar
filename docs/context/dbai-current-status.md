# dbai current status

Status snapshot: 2026-03-17

## Current Stage

`DBAI-Domain-Based-Agent-Identity` is an early-stage spec and convention repo. Its current position is `v0.1 current`, with a roadmap toward operational hardening and eventually a frozen `v1.0` identity core.

## What It Does

DBAI defines a minimal identity discovery layer for digital actors and agents. It uses:

- a domain as a durable anchor
- an agent manifest as the discovery document
- decentralized resolvers as the validation mechanism

Its purpose is to make an actor discoverable and anchorable across platforms and runtimes without requiring a centralized registry.

## Canonical Docs

- `README.md`
- `ABSTRACT.md`
- `VISION.md`
- `DESIGN_PRINCIPLES.md`
- `OOSITIONING.md`
- `FAQ..md`
- `resolver/resolver-checklist.md`

## Core Model

The repo consistently describes the same core model:

- `domain` provides the durable anchor and namespace context
- `agent-manifest.json` publishes controllers, endpoints, and proof
- `resolver` behavior validates anchor consistency and proof
- identity is intentionally separated from capability, semantics, and reputation
- extensions may exist, but unknown extensions must remain opaque to identity validity

The trust model is intentionally minimal:

- Name Control
- Key Control
- Capability Control

DBAI only standardizes the first two enough to make discovery and binding possible.

## What DBAI Does Not Do

DBAI does not try to be:

- a full SSI stack
- a centralized registry
- a capability taxonomy
- a reputation framework
- a runtime attestation system
- a complete credential semantics layer

It is a glue layer, not a total identity solution.

## Current Open Questions

Based on the roadmap and current positioning docs, the main open questions are operational rather than conceptual:

- how key rotation and revocation patterns should be documented
- what cache and TTL guidance should become standard
- how multi-agent or multi-runtime namespace delegation should work
- how far schema discovery hints should go without turning into hard dependencies
- how much future interop guidance belongs inside the core versus adjacent docs

## Next Step

The next planned batch implied by the repo roadmap is `v0.2 Operational Hardening`, including guidance for key rotation, revocation pointers, cache and TTL handling, DNSSEC or registry-lock operational notes, and multi-agent namespace patterns.

## Deferred

- centralized index as a dependency for identity existence
- capability taxonomy and action semantics
- reputation and trust scoring systems
- making schema retrieval mandatory for resolver validity
- turning DBAI into a platform-bound identity service

## GPT Notes

- Frame DBAI as an identity discovery convention, not as a deployed app or hosted service.
- Keep the distinction between `anchor`, `control`, and `capability` clear.
- When comparing DBAI to DID or wallet identity, present it as complementary rather than competitive.
- Prefer the resolver checklist when questions are about implementation behavior and the positioning docs when questions are about scope.
