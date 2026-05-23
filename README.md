# Agentic AI Analytics Platform

[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/)
[![CI](https://github.com/saikirankonda99/agentic-ai-analytics-platform/actions/workflows/ci.yml/badge.svg)](https://github.com/saikirankonda99/agentic-ai-analytics-platform/actions/workflows/ci.yml)
[![Tests](https://img.shields.io/badge/tests-pytest-green.svg)](tests)
[![Lint](https://img.shields.io/badge/lint-ruff-green.svg)](pyproject.toml)
[![E2E](https://img.shields.io/badge/e2e-playwright-green.svg)](tests/e2e)
[![License](https://img.shields.io/badge/license-not%20specified-lightgrey.svg)](#license)

Agentic AI Analytics Platform is a production-oriented natural-language analytics workspace. It combines a Streamlit operator UI, a FastAPI control plane, safe SQL generation, workflow telemetry, workspace persistence, connector diagnostics, and browser-based regression testing.

The project is intentionally scoped as an engineering reference implementation: it favors explicit orchestration, validation, diagnostics, and testability over opaque automation.

## Live Links

- Live deployment: https://agentic-ai-analytics-platform.onrender.com
- Repository: https://github.com/saikirankonda99/agentic-ai-analytics-platform
- Author: Sai Kiran Konda

## Platform Overview

The workspace supports natural-language analytics against the bundled Chinook SQLite dataset, CSV uploads, and connector-ready database boundaries. It preserves workspace state across sessions and exposes operational views for query execution, orchestration status, telemetry, investigations, monitoring, API diagnostics, and saved history.

Core surfaces:

| Area | Purpose |
|---|---|
| `Overview` | Query workflow, result explorer, charts, insight brief, SQL trace, exports |
| `Operations` | Runtime health, workflow queue, execution graph, telemetry trends |
| `Copilot` | Conversation history, workflow timeline, telemetry panel |
| `Investigations` | Autonomous drill-down state, pinned investigations, saved assets |
| `Monitoring` | Scheduled KPI checks, executive briefing state, monitoring run history |
| `Agents` | Agent status, SQL intelligence, latency breakdown, reasoning snapshots |
| `API` | Runtime diagnostics, connector health, endpoint map, telemetry search |
| `History` | Saved SQL, bookmarks, reports, recent activity, workspace continuity |

## Architecture Summary

```text
Streamlit workspace
  -> session/auth/workspace state
  -> command and dashboard views
  -> local orchestration runner

FastAPI backend
  -> health/readiness/diagnostics
  -> auth, connector, workspace, telemetry, workflow APIs
  -> persistence repositories

Runtime layer
  -> schema grounding
  -> memory retrieval
  -> SQL generation and validation
  -> execution, insight, investigation
  -> telemetry and replay metadata

Persistence and connectors
  -> SQLite fallback
  -> PostgreSQL-ready repositories
  -> connector diagnostics and schema inspection
```

Detailed Mermaid diagrams are in [Architecture Diagrams](docs/architecture.md).

## Core Capabilities

- Natural-language analytics workflow with SQL inspection and result exploration.
- Safe SQL guardrails with SELECT-only enforcement and destructive operation blocking.
- SQL intelligence pipeline for schema reasoning, validation, explanation, recovery, and result quality.
- Orchestration timeline, execution graph, phase confidence, and recovery diagnostics.
- Workspace persistence for sessions, query history, bookmarks, investigations, reports, preferences, and onboarding state.
- Lightweight collaboration with personal/team workspace switching, shared reports, shared investigations, shared bookmarks, and collaboration activity.
- Telemetry normalization for latency, token usage, estimated cost, correlation IDs, retries, and error metadata.
- Connector diagnostics for SQLite/PostgreSQL posture and API-level health visibility.
- CSV upload analysis with the same workspace, telemetry, exports, and persistence surfaces.
- Browser E2E tests covering auth, onboarding, analytics, exports, diagnostics, persistence, monitoring, and operations.

## Orchestration Lifecycle

The workflow is explicit and inspectable:

1. Planner normalizes the request and detects follow-up context.
2. Schema retrieval grounds the query against connector metadata.
3. Memory retrieval brings in relevant workspace history.
4. SQL generation runs through the LLM abstraction layer.
5. SQL validation enforces syntax, read-only behavior, and execution policy.
6. Reflection/recovery captures retry and degradation decisions.
7. Execution runs through the connector boundary.
8. Insight generation summarizes result signals.
9. Investigation runs drill-down workflows when severity warrants it.
10. Persistence records workflow, telemetry, reports, bookmarks, and replay context.

See [Orchestration Lifecycle](docs/orchestration-lifecycle.md) and [Multi-Agent Orchestration](docs/multi-agent-orchestration.md).

## SQL Intelligence Pipeline

SQL generation is not treated as a trusted final answer. The platform records:

- schema intelligence and selected tables/columns
- generated SQL
- validation status, warnings, and risk score
- retry and recovery metadata
- SQL explanation
- result quality checks

See [SQL Intelligence](docs/sql-intelligence.md).

## Telemetry And Observability

Telemetry is normalized through `backend.telemetry` and rendered in Streamlit and FastAPI diagnostics. The platform tracks:

- correlation ID
- workflow phase and status
- latency by phase
- token usage and estimated cost
- model metadata
- retry state and policy decisions
- structured error type/message
- telemetry export rows

Telemetry can be downloaded from the workspace as JSON/CSV and inspected through API diagnostics. See [Platform Control Plane](docs/platform-control-plane.md) and [E2E Testing](docs/e2e-testing.md).

## Persistence And Workspace Architecture

The runtime separates platform persistence from workflow persistence:

| Store | Default | Responsibility |
|---|---|---|
| `DATABASE_URL` | `sqlite:///data/platform_persistence.db` | auth sessions, workspace memory, saved reports, bookmarks, onboarding, preferences |
| `WORKFLOW_DATABASE_URL` | `sqlite:///data/workflow_runtime.db` | workflows, events, telemetry, usage, agent metadata |

SQLite works for local development. PostgreSQL is supported for production-oriented deployments and is validated at startup. See [PostgreSQL Persistence](docs/postgresql-persistence.md).

## Collaboration Workflows

Users can switch between a personal workspace and a shared team workspace from the Streamlit sidebar. Shared reports, investigations, bookmarks, and dashboard views retain owner, creator, visibility, and updated-at metadata. Recent collaboration activity is rendered in the History workspace so saved analysis has visible team context without adding heavy RBAC.

The permissions model is intentionally small: admins and analysts can share, viewers can inspect shared context but receive graceful warnings when trying to share. See [Collaboration Workflows](docs/collaboration.md).

## Connectors And Diagnostics

The connector layer exposes registration, health checks, schema inspection, and safe configuration diagnostics. FastAPI provides:

- `GET /health`
- `GET /ready`
- `GET /diagnostics`
- `GET /connectors`
- `GET /connectors/{connector_id}/health`
- `GET /connectors/{connector_id}/schema`
- `POST /connectors/validate`

See [Connectors](docs/connectors.md) and [Deployment](docs/deployment.md).

## Onboarding, Reports, And Exports

The Streamlit workspace includes:

- persisted onboarding checklist
- guided sample prompts
- sortable/filterable result explorer
- filtered and full CSV downloads
- executive summary export
- workflow trace export
- telemetry JSON/CSV export
- saved reports, query bookmarks, pinned investigations
- workspace restoration after reload

Demo flow details are in [Demo Walkthrough](docs/demo-walkthrough.md).

## Screenshots

Screenshot folders are prepared for portfolio and release assets:

| Area | Path | Recommended capture |
|---|---|---|
| Onboarding | `screenshots/onboarding/` | first-run checklist and guided query state |
| Orchestration | `screenshots/orchestration/` | timeline, execution graph, agent status |
| Telemetry | `screenshots/telemetry/` | observability cards, latency breakdown, telemetry export |
| Reports | `screenshots/reports/` | result explorer, exports, saved reports |
| Connectors | `screenshots/connectors/` | API diagnostics, connector health, endpoint map |
| Collaboration | `screenshots/collaboration/` | shared workspace switcher, shared report history, owner metadata |

Recommended first captures:

- `screenshots/onboarding/01-onboarding-workspace.png`
- `screenshots/orchestration/01-workflow-timeline.png`
- `screenshots/orchestration/02-sql-intelligence.png`
- `screenshots/telemetry/01-observability-panel.png`
- `screenshots/reports/01-result-explorer.png`
- `screenshots/reports/04-shared-report-history.png`
- `screenshots/collaboration/01-shared-workspace-history.png`
- `screenshots/connectors/01-api-diagnostics.png`

Naming guidance is in [Screenshots Guide](screenshots/README.md). Avoid committing local Playwright failure screenshots from `test-results/`.

## Local Setup

Use Python 3.11.

```bash
git clone https://github.com/saikirankonda99/agentic-ai-analytics-platform.git
cd agentic-ai-analytics-platform
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Configure environment:

```bash
cp .env.example .env
```

For OpenAI-backed SQL generation, set:

```bash
OPENAI_API_KEY=your_api_key_here
```

The app can still run without an API key for diagnostics, onboarding, CSV-backed workflows, and most local tests.

Start Streamlit:

```bash
python -m streamlit run app.py --server.port 8501
```

Start FastAPI:

```bash
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Validate health:

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/diagnostics
curl http://127.0.0.1:8501/_stcore/health
```

## Persistence Setup

SQLite fallback:

```bash
DATABASE_URL=sqlite:///data/platform_persistence.db
WORKFLOW_DATABASE_URL=sqlite:///data/workflow_runtime.db
```

PostgreSQL:

```bash
DATABASE_URL=postgresql://app_user:password@localhost:5432/agentic_ai
WORKFLOW_DATABASE_URL=postgresql://app_user:password@localhost:5432/agentic_ai
```

The startup validator reports persistence backend, configuration source, and schema bootstrap status. See [PostgreSQL Persistence](docs/postgresql-persistence.md).

## Docker

Local stack:

```bash
docker compose up --build
```

Individual image:

```bash
docker build -t agentic-ai-analytics-platform .
docker run --rm -p 8501:8501 --env-file .env agentic-ai-analytics-platform
```

Backend image and frontend image are also available through `Dockerfile.backend` and `Dockerfile.frontend`.

## Testing

Fast local validation:

```bash
python -m ruff check .
python -m pytest
```

Playwright setup:

```bash
python -m playwright install chromium
```

Run browser E2E:

```bash
RUN_E2E=1 python -m pytest tests/e2e
```

On Windows PowerShell:

```powershell
$env:RUN_E2E="1"
python -m pytest tests/e2e
```

The default E2E suite uses a deterministic CSV-backed analytics workflow. The OpenAI-backed SQL generation test is marked `openai` and only runs when `OPENAI_API_KEY` is configured.

## CI/CD

GitHub Actions runs:

- `lint`: Ruff checks
- `test`: pytest suite
- `startup`: FastAPI and Streamlit startup probes
- `e2e`: Playwright browser tests with artifacts
- `docker`: backend/frontend image build validation
- `deployment-safety`: deployment file checks

See [CI/CD Runtime Validation](docs/cicd-runtime-validation.md).

## Documentation Map

- [Docs Index](docs/README.md)
- [Architecture Diagrams](docs/architecture.md)
- [Demo Walkthrough](docs/demo-walkthrough.md)
- [Collaboration Workflows](docs/collaboration.md)
- [Performance Notes](docs/performance.md)
- [Screenshots Guide](screenshots/README.md)
- [Deployment](docs/deployment.md)
- [E2E Testing](docs/e2e-testing.md)
- [Troubleshooting](docs/troubleshooting.md)

## Roadmap

Near-term:

- capture and commit curated screenshots for the prepared screenshot structure
- expand role-specific browser tests for admin, analyst, and viewer
- add more connector-specific E2E fixtures
- improve report templates for repeatable demo artifacts
- add a lightweight seed-data reset command for demos

Future:

- broaden SQL evaluation datasets
- add more database connectors
- improve semantic retrieval for longer workspace histories
- add workflow comparison and replay UI
- support external worker execution for longer-running jobs
- define an explicit repository license

## License

No license file is currently declared. Add a `LICENSE` file before treating this repository as open-source software.

## Author

Sai Kiran Konda

- LinkedIn: https://www.linkedin.com/in/sai-kiran-konda/
- GitHub: https://github.com/saikirankonda99
- Email: saikiran1.konda@gmail.com
