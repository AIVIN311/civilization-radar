# Security Policy

## Project Scope

Civilization Radar is an observation-first research project.

It does not provide:
- A public API
- A hosted service
- User authentication
- Data ingestion endpoints
- External write interfaces

All data collection and processing run locally on the operator's machine.

## Supported Versions

This project operates under a rolling baseline model.

Only the latest `main` branch is considered supported.
Historical versions are preserved for reproducibility but are not actively maintained.

## Data & Runtime Model

- Runtime files (e.g., `input/snapshots.jsonl`, `output/`) are not tracked by Git.
- No user data is collected.
- No external credentials are stored in the repository.

Operators are responsible for securing:
- Their local environment
- Cloudflare tokens (if used)
- Git credentials

## Reporting a Vulnerability

If you believe you have discovered a security issue related to:

- Code execution
- Dependency misuse
- Sensitive data exposure
- Misconfiguration risks

Please open a GitHub issue with the label `security`.

This project is maintained on a best-effort basis.
There is no SLA or guaranteed response time.

---

This repository is intended for research and observation purposes only.
It should not be used as a production security monitoring system.
