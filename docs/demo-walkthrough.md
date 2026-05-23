# Demo Walkthrough

This walkthrough is designed for a five-to-ten minute repository demo. It shows the platform as an engineering system rather than a prompt demo.

## Recommended Demo Data

- Use the bundled Chinook SQLite dataset for SQL generation, validation, result tables, and schema-aware workflow visibility.
- Use a small synthetic revenue CSV when you want a deterministic browser demo that does not depend on an LLM key.
- Avoid private datasets, customer examples, API keys, local file paths, and personally identifiable information in screenshots or recordings.

## Five-Minute Timing

| Time | Segment | Goal |
|---|---|---|
| 0:00-0:40 | Onboarding and workspace | Establish the product surface and persisted workspace state |
| 0:40-1:35 | Analytics query | Show question submission, loading state, result table, and chart |
| 1:35-2:20 | Orchestration | Show timeline, execution graph, and recovery/status visibility |
| 2:20-3:00 | SQL intelligence | Show generated SQL, validation state, explanation, and quality checks |
| 3:00-3:40 | Telemetry and exports | Show correlation ID, latency/cost telemetry, and export actions |
| 3:40-4:25 | Collaboration and persistence | Share a report, switch workspace scope, refresh, and reopen History |
| 4:25-5:00 | Diagnostics | Show API health, connector diagnostics, and CI/E2E coverage |

## 1. Start With The Workspace

Open Streamlit and log in with the configured admin user.

Call out:

- workspace navigation
- onboarding checklist
- guided query buttons
- sidebar controls
- API/runtime readiness

Recommended screenshot: `screenshots/onboarding/01-onboarding-workspace.png`

## 2. Run An Analytics Workflow

Use either:

- bundled prompt: `Revenue by Country`
- CSV-backed demo: upload a small revenue CSV and submit `Summarize uploaded revenue by country`

Call out:

- command workspace
- loading/live execution panel
- result table
- chart or KPI rendering
- SQL trace when using database-backed generation

Recommended screenshot: `screenshots/reports/01-result-explorer.png`

## 3. Show Orchestration Visibility

Move to `Operations` or `Copilot`.

Call out:

- workflow timeline
- execution graph
- active agent monitoring
- retry/recovery surfaces
- workflow queue

Recommended screenshot: `screenshots/orchestration/01-workflow-timeline.png`

## 4. Explain SQL Intelligence

Move to `Agents`.

Call out:

- SQL validation state
- schema confidence
- risk score
- SQL explanation
- result quality warnings
- latency breakdown

Recommended screenshot: `screenshots/orchestration/02-sql-intelligence.png`

## 5. Show Telemetry And Exports

From `Overview`, `Agents`, or `API`, show observability panels and export buttons.

Call out:

- correlation ID
- latency
- token/cost telemetry when available
- JSON/CSV telemetry export
- executive summary export
- workflow trace export

Recommended screenshot: `screenshots/telemetry/01-observability-panel.png`

## 6. Save Workspace Artifacts

In `Overview`, click:

- `Bookmark Query`
- `Save Report View`
- `Share Report`
- `Pin Investigation` when investigation state exists

Then navigate to `History`.

Call out:

- saved SQL history
- saved reports
- shared visibility and owner metadata
- recent collaboration activity
- recent activity
- workspace continuity

Recommended screenshot: `screenshots/reports/02-saved-reports.png`

Recommended collaboration screenshot: `screenshots/collaboration/01-shared-workspace-history.png`

## 7. Validate Persistence Reload

Refresh the browser and return to `History`.

Call out:

- restored session state
- persisted reports and bookmarks
- workspace memory boundaries
- onboarding persistence

## 8. Show Diagnostics

Move to `API`.

Call out:

- `/health`, `/ready`, `/diagnostics`
- connector diagnostics
- OpenAI runtime posture
- workspace inspection
- telemetry event search

Recommended screenshot: `screenshots/connectors/01-api-diagnostics.png`

## Best Demo Order

1. Onboarding
2. Analytics query
3. Orchestration timeline
4. SQL intelligence
5. Telemetry/export
6. Shared report/bookmark
7. Refresh and restore
8. API diagnostics

## Collaboration Add-On

For a team workflow demo:

1. Run a query in the personal workspace.
2. Save and share a report.
3. Switch the sidebar scope to `Shared team`.
4. Open `History`.
5. Show `Recent Collaboration`, shared report indicators, owner metadata, and updated timestamps.

This order shows product value first, then engineering depth, then operational readiness.
