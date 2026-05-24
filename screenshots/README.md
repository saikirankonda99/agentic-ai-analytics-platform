# Screenshots Guide

This directory is reserved for curated screenshots used in the README, portfolio writeups, release notes, and demos.

Do not commit local Playwright failure artifacts from `test-results/`. Curated screenshots should be captured from a clean local run with representative but non-sensitive data.

## Folder Structure

| Folder | Content |
|---|---|
| `onboarding/` | first-run workspace, onboarding checklist, guided query state |
| `orchestration/` | workflow timeline, execution graph, agent panels, SQL intelligence |
| `telemetry/` | observability cards, latency breakdowns, telemetry exports |
| `reports/` | result explorer, CSV export, executive summary export, saved reports |
| `connectors/` | API diagnostics, connector health, endpoint map, telemetry search |
| `collaboration/` | shared workspace scope, shared reports, owner metadata, collaboration history |

## Naming Convention

Use:

```text
NN-short-description.png
```

Examples:

```text
screenshots/onboarding/01-onboarding-workspace.png
screenshots/orchestration/01-workflow-timeline.png
screenshots/telemetry/01-observability-panel.png
screenshots/reports/01-result-explorer.png
screenshots/reports/04-shared-report-history.png
screenshots/connectors/01-api-diagnostics.png
screenshots/collaboration/01-shared-workspace-history.png
```

## Capture Guidance

- Use a desktop viewport around `1440x900`.
- Prefer the seeded Chinook dataset or a small synthetic CSV.
- Hide browser bookmarks and unrelated OS chrome when possible.
- Capture after the workflow has completed, unless the screenshot is specifically about loading state.
- Avoid screenshots with real API keys, private database URLs, personal data, or local filesystem paths.
- Keep filenames stable so README references do not churn.

## Priority Capture List

| Path | Purpose |
|---|---|
| `onboarding/01-onboarding-workspace.png` | first-run checklist and workspace navigation |
| `orchestration/01-workflow-timeline.png` | completed workflow timeline and execution status |
| `orchestration/02-sql-intelligence.png` | generated SQL, validation, explanation, and quality checks |
| `telemetry/01-observability-panel.png` | correlation ID, latency, retry state, and telemetry export |
| `reports/01-result-explorer.png` | result table, chart, CSV export, and report actions |
| `reports/04-shared-report-history.png` | shared saved report with visibility and owner metadata |
| `collaboration/01-shared-workspace-history.png` | shared team workspace, collaboration activity, and persisted assets |
| `connectors/01-api-diagnostics.png` | health/readiness diagnostics and connector posture |
