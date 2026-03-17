# concept-markers current status

Status snapshot: 2026-03-17

## Current Stage

The repo is in a contract-driven static maintenance phase. It behaves more like a governed site network than a feature-heavy application: public pages, topology rules, generation scripts, and audit steps are the main operating surface.

## What It Does

`concept-markers` publishes static concept pages connected by a shared footer network. It uses:

- `domains.json` as the canonical domain inventory
- `networklayer/markers.js` as the shared marker source
- `RELATIONAL_LAYER.md` and `ops/*` maps to describe structural intent

There is no backend, API server, or database in the normal model.

## Canonical Docs

- `README.md`
- `RELATIONAL_LAYER.md`
- `AGENTS.md`
- `ops/governance-layer-map.md`
- `ops/identity-radar-map.md`
- `package.json` for verification commands

## How It Works

- Each concept lives in a folder with `index.html`.
- Shared footer and network behavior come from `networklayer/markers.js`.
- Domain inventory and generation flow are driven from `domains.json`, not folder scanning.
- Standard repo verification is `npm run verify:all`.
- Key internal checks include:
  - `npm run domains:validate`
  - `npm run markers:audit:strict`
  - sitemap and robots generation
  - `npm run format:check`

## Current Issues

Latest local review identified four operational gaps:

- `markers:audit:strict` does not currently fail on `hosts_missing_in_pages`
- local preview can mis-detect the current host and fail to suppress self-links in the footer
- sitemap `lastmod` does not reflect shared footer changes because it only tracks per-page commits
- `npm run verify:all` is not currently a clean release gate because it ends in `format:check` failures across tracked files

## Recent Findings

- The repo structure is coherent and well-documented for static operations.
- The shared marker and topology model are strong, but verification still has blind spots.
- Current findings point more to audit and release-discipline cleanup than to architecture failure.
- Review was read-only; no repo changes were made as part of that pass.

## Next Step

No repo-official implementation batch is locked in from the canonical docs currently loaded here. The practical next step for support planning is to restore verification trust by tightening audit behavior and deciding whether formatting drift should be cleaned or intentionally deferred.

## Deferred

- Any move toward backend, API, database, or app-style runtime
- Large-scale content rewrites that are not tied to topology or verification needs
- Broad refactors that would change marker-footer compatibility without a deliberate contract update

## GPT Notes

- Treat this repo as static-first and contract-driven.
- Prefer `README.md`, `RELATIONAL_LAYER.md`, and `AGENTS.md` over ad hoc notes when answering how the repo works.
- Do not imply there is a backend service unless the repo changes materially.
- When asked about health, mention both the intended verification flow and the latest known gaps in `verify:all`.
