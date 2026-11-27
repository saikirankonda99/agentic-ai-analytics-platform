# Agentic AI Analytics Platform

[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/)
[![CI](https://github.com/saikirankonda99/agentic-ai-analytics-platform/actions/workflows/ci.yml/badge.svg)](https://github.com/saikirankonda99/agentic-ai-analytics-platform/actions/workflows/ci.yml)
[![Tests](https://img.shields.io/badge/tests-pytest-green.svg)](tests)
[![Lint](https://img.shields.io/badge/lint-ruff-green.svg)](pyproject.toml)
[![E2E](https://img.shields.io/badge/e2e-playwright-green.svg)](tests/e2e)
[![License](https://img.shields.io/badge/license-not%20specified-lightgrey.svg)](#license)

Agentic AI Analytics Platform (Sales Studio) combines a customer sales dashboard, an administrator workspace, a real queued analytics API, and durable PostgreSQL/SQLite storage. Customers can review sales CSVs, check exact totals, explore charts, and download reports. The separate AI workflow generates validated, read-only SQL against an explicitly authorized database.

The repository is a release candidate with explicit validation gates. See [Release readiness](docs/release-readiness.md) for what is implemented, what automated checks cover, and the remaining live AI, hosted deployment, and business-data acceptance steps.

For the saved release revision, completed checks, hosting status, and next steps, see the [project checkpoint](docs/project-checkpoint.md).

## Small-business sales demo

Load the included synthetic retail dataset, ask a supported sales question, inspect the answer, and export the result. **No API key is needed for CSV calculations.**

1. Follow [Local Setup](#local-setup), then start Streamlit.
2. For local development, sign in as `admin` with `admin123`, or the password configured in `AUTH_ADMIN_PASSWORD`.
3. In the default **Customer dashboard**, click **Try sample data**. An initial sales summary opens.
4. Expand **Common questions**, then click **Revenue by Product**, **Monthly Revenue**, or **Total Revenue**.
5. Choose **Download results CSV** or **Download summary** below the answer.

The customer dashboard uses a three-step sales flow and warm ivory/plum styling with decorative CSS 3D artwork. Only authenticated administrators can open the separate **Admin workspace**. See [Customer and Administrator Experience](docs/customer-admin-experience.md) for exact screen text, component notes, and the demo checklist.

The 12 sample transactions total **352.00 USD**. Product totals are Coffee Beans **180.00**, Tea **100.00**, and Mug **72.00**. Monthly totals are January **144.00**, February **117.00**, and March **91.00**. These are synthetic demonstration results, not customer outcomes.

For your own CSV, choose **Upload**, preview the first 10 rows, match the sales fields to your columns, and choose **Use this data** after reviewing the checks and total. Choose whether revenue comes from a line-amount column or quantity × unit price, and select the date format and currency when needed. The entire upload is validated before it becomes active.

Own-file uploads support total revenue, revenue by product/month/country, units sold by product, and a sales summary, depending on the columns selected. Every row is included in the calculation. Unsupported questions receive a message instead of an unrelated answer. See [Sales Demo and Milestone Status](docs/small-business-milestone.md) for the CSV contract, validation, and remaining work.

### Current implementation boundaries

| Path | Current behavior |
|---|---|
| Sales CSV in Streamlit | Local deterministic aggregation, charts, result exports, and saved workspace metadata |
| Optional CSV AI review | Explicit OpenAI request to prioritize verified aggregate facts and suggested checks; requires a server-side API key. No raw rows, arbitrary Q&A, causal claims, or automatic business actions |
| Database questions in Streamlit | Model-generated SQL against the bundled example database; requires an API key and live-model evaluation |
| FastAPI `POST /execute` | Authenticated, authorized real analytics queued durably; poll workflow status and `/result`. The lifecycle demo is separately labeled at `/execute/simulation` |
| Monitoring | Example-database checks triggered while the app is active; no durable background scheduler |
| Background execution | SQL-backed worker with leases, retries, idempotency, and restart recovery; separate maintenance process enforces retention |
| Memory | Persistent workspace/connector-scoped lexical retrieval in SQLite/PostgreSQL; optional implemented pgvector storage |
| Customer data | Explicit connector grants, scoped saved records, deletion controls, backup/restore tooling, and fail-closed production storage; hosted acceptance remains a separate gate |

Use synthetic data for the demo. Production mode requires explicit users with hashed passwords and refuses the development login defaults. See [Deployment](docs/deployment.md), [Actual analytics API](docs/actual-api.md), [Data isolation](docs/data-isolation.md), and [Operations and recovery](docs/operations.md).

## Live Links

- Existing demo URL: https://agentic-ai-analytics-platform.onrender.com (the deployed revision must be verified separately)
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
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-lock.txt
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

### Windows PowerShell: retail demo

From the repository folder, use the Python 3.11 launcher and the virtual environment's interpreter directly. No PowerShell activation-policy change is needed:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv\Scripts\python.exe -m streamlit run app.py --server.port 8501
```

Open `http://localhost:8501`, sign in with the development credentials above, and choose **Try sample data** in the customer dashboard. CSV calculations do not require an `.env` file, a separate FastAPI process, or an API key; the optional AI review does require a key. The lock file excludes the optional `uvloop` dependency on Windows. Native Windows installation has not been exercised by the Linux CI jobs.

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
curl http://127.0.0.1:8501/_stcore/health
```

Private API endpoints require a valid session from `POST /auth/login`. Send its token as `X-Session-Token` or `Authorization: Bearer ...`. Diagnostics and connector endpoints require an admin role; workspace endpoints check ownership and write permissions.

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
# Configure AUTH_USERS and a URL-safe POSTGRES_PASSWORD first; see Deployment.
docker compose up --build --wait
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
- `docker`: backend/frontend image builds and complete stack authentication/worker checks
- `persistence-services`: real PostgreSQL, pgvector, private read-only role, and backup/restore checks
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
