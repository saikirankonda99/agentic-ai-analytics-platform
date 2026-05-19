# Usability and Onboarding Guide

This guide describes the product-facing workspace flow for first-time users, analysts, and operators.

## First Run

1. Open the Streamlit app and sign in with a local workspace identity.
2. Review the onboarding card on the Overview workspace.
3. Keep the bundled Chinook sample dataset active or upload a CSV from the sidebar.
4. Run a guided query such as `Revenue by country` or `Top 10 customers by invoices`.
5. Inspect the generated SQL, result explorer, chart, workflow timeline, and AI insight brief.
6. Export the filtered CSV, executive summary, telemetry bundle, or workflow trace.

Onboarding progress is stored in workspace memory so returning users resume where they left off.

## Workspace Walkthrough

- `Overview`: primary analytics workspace with guided prompts, result explorer, charts, recovery guidance, and exports.
- `Operations`: runtime health, workflow queues, operational KPIs, telemetry trends, and report exports.
- `Copilot`: chat transcript, workflow timeline, and model telemetry.
- `Investigations`: autonomous drill-downs, bookmarks, pinned investigations, and follow-up context.
- `Monitoring`: scheduled KPI checks and executive briefing state.
- `Agents`: active agent states, reasoning snapshots, validation state, and latency breakdowns.
- `API`: backend diagnostics, connector posture, endpoint map, and workspace export controls.
- `History`: saved SQL, bookmarks, report views, recent activity, and session continuity.

## Analytics Workflow Examples

- Revenue posture: `Revenue by country`
- Customer concentration: `Top 10 customers by invoices`
- Product exploration: `Tracks with album and artist`
- Follow-up refinement: `Only show the top regions from the previous result`
- Operational monitoring: enable scheduled checks, select KPI targets, then run a scheduled check.

## Result Explorer

The result explorer supports:

- row filtering across visible cell values
- column sorting
- filtered CSV export
- full CSV export
- persistent query bookmarks
- saved executive report views

Use bookmarks for reusable SQL workflows. Use saved reports for snapshots that need to survive session changes.

## Recovery Guidance

When a workflow fails, check the recovery guidance card first. It consolidates:

- OpenAI runtime failures and retry hints
- SQL validation warnings
- connector troubleshooting hints
- execution policy recovery messages

For persistent connector failures, validate connector health from the API workspace and verify credentials, schema access, and local database availability.

## Deployment Walkthrough

1. Configure environment variables from `.env.example`.
2. Validate locally with `python -m ruff check` and `python -m pytest`.
3. Start the backend with `python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000`.
4. Start Streamlit with `python -m streamlit run app.py --server.headless true`.
5. Check `/health`, `/ready`, and `/diagnostics` before exposing the service.

Keep Streamlit and FastAPI deployed as separate processes so the UI can restart independently from orchestration APIs.
