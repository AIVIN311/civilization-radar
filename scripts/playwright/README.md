# Playwright Dashboard Workflow

Automates the local `output/latest/dashboard_v04.html` interaction flow with Playwright and writes artifacts to `output/playwright/`.

## What it does
- Opens the dashboard from a local file path.
- Validates the domain table renders.
- Applies the `事件` filter.
- Searches for `algorithmicallocation`.
- Expands a `Matched` row details panel.
- Resets filters.
- Toggles `風暴模式` when present.
- Expands a `Top-3` row when present.
- Saves screenshots and a JSON run summary.

## Run
```bash
npm run playwright:dashboard
```

Headed mode:
```bash
npm run playwright:dashboard:headed
```

Custom file path:
```bash
node scripts/playwright/dashboard_workflow.mjs --dashboard output/latest/dashboard_v04.html
```

## Artifacts
- `output/playwright/01-initial.png`
- `output/playwright/02-event-filter.png`
- `output/playwright/03-search.png`
- `output/playwright/04-match-expanded.png`
- `output/playwright/05-final.png`
- `output/playwright/dashboard-workflow-summary.json`
