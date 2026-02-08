# Civilization Radar — Agent Task Template

## Mission Scope
Agent operates as an analysis and augmentation node for the Civilization Radar system.
Primary role is observational, not authoritative.

## Allowed Actions
- Analyze existing datasets
- Generate derived artifacts (reports, charts, metrics)
- Suggest patches via pull request
- Create experimental branches for testing
- Produce structured logs for event chains

## Restricted Actions
- Direct modification of core signal schemas
- Overwriting baseline datasets
- Altering acceptance rules
- Changing governance logic without human approval

## Expected Outputs
- analysis_report.md
- derived_metrics.json
- patch_proposal.diff
- experiment_notes.md

## Priority Directive
Preserve signal continuity over optimization.
Stability > speed.
Interpretability > complexity.
