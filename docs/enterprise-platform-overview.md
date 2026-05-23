# Enterprise Platform Overview

Agentic AI Analytics Platform is an enterprise AI analytics orchestration system for governed natural language analytics, safe SQL execution, autonomous investigation, workflow observability, and operational reporting.

The platform is structured as an AI data operations workspace rather than a single text-to-SQL interface. Streamlit provides the operator workspace. FastAPI provides orchestration, diagnostics, connector, telemetry, governance, audit, and workspace APIs. The orchestration runtime coordinates planning, schema grounding, memory retrieval, SQL generation, validation, reflection, execution, insight generation, and investigation.

## Architecture Overview

```text
Operator / Analyst
      |
      v
Streamlit Enterprise Workspace
      |
      | workspace state, auth session, command workflow, dashboards
      v
FastAPI Control Plane
      |
      | lifecycle APIs, auth session support, diagnostics, connectors,
      | governance, scheduler, audit, telemetry exports
      v
Orchestration Runtime
      |
      | planner -> schema -> memory -> SQL -> validation -> reflection
      | -> execution -> insight -> investigation
      v
Data and AI Runtime
      |
      | SQLite / PostgreSQL connectors, OpenAI runtime layer,
      | semantic memory, workspace persistence
```

### Frontend Boundary

The Streamlit workspace owns the operational user experience:

- authenticated workspace shell
- command submission
- orchestration status views
- telemetry exports
- investigation workspace
- monitoring workspace
- agent dashboards
- API and diagnostics panels
- history and replay surfaces

Streamlit does not call OpenAI directly. Model access remains isolated behind `llm.py`.

### Backend Boundary

FastAPI owns platform control-plane capabilities:

- health, readiness, and runtime diagnostics
- workflow lifecycle APIs
- execution graph and replay APIs
- connector health, validation, and schema inspection
- auth session endpoints
- workspace persistence endpoints
- governance, scheduler, incidents, audit, and executive reporting APIs

### Runtime Boundary

`graph.workflow` owns deterministic orchestration phases. It returns structured workflow state with SQL, result rows, trace, telemetry, execution graph metadata, confidence, recovery hints, and policy decisions.

## Orchestration Lifecycle

The workflow lifecycle is intentionally explicit and inspectable:

1. `planner`: normalizes the user question and detects follow-up context.
2. `schema retrieval`: loads connector schema metadata.
3. `memory retrieval`: retrieves relevant prior workflow examples.
4. `sql generation`: generates SQL through the OpenAI runtime layer.
5. `validation`: enforces read-only SQL safety.
6. `reflection`: repairs failed SQL when retry budget remains.
7. `execution`: executes validated SQL through the connector boundary.
8. `autonomous insight`: scans result sets for operational signals.
9. `investigation`: runs drill-down queries when anomaly severity warrants it.

Agent states are normalized as:

- `queued`
- `running`
- `retrying`
- `completed`
- `failed`
- `skipped`

Execution graph metadata is exposed through:

```text
GET /workflow/{workflow_id}/execution-graph
GET /workflow/{workflow_id}/replay
GET /workflow/{workflow_id}/events
```

The graph response includes node status, dependency readiness, completion rates, confidence rollups, and replay frames derived from lifecycle events.

For the SQL-specific validation, schema reasoning, repair, explainability, and quality pipeline, see `docs/sql-intelligence.md`.

## Telemetry Flow

Telemetry is collected at each runtime boundary and normalized before export.

```text
Workflow node
  -> step telemetry
  -> backend.telemetry validation
  -> Streamlit dashboards / FastAPI APIs
  -> export rows / aggregate metrics / incident signals
```

Tracked telemetry includes:

- correlation ID
- schema version
- phase latency
- prompt tokens
- completion tokens
- total tokens
- estimated cost
- model name
- usage availability
- error type and message
- retry attempt metadata
- structured exception details

Primary telemetry surfaces:

```text
GET /telemetry/schema
GET /workflow/{workflow_id}/telemetry
GET /workflow/{workflow_id}/telemetry/events
GET /workflow/{workflow_id}/telemetry/aggregate
```

The telemetry aggregation layer groups events by phase and reports failure rate, cost, latency, token usage, and failure category.

## Investigation System

The investigation system converts high-signal analytics findings into persistent drill-down workflows.

Investigation lifecycle:

```text
insight finding
  -> planning
  -> targeted SQL generation
  -> guardrail validation
  -> evidence collection
  -> summary and confidence score
  -> workspace persistence
```

Investigation state includes:

- lifecycle events
- generated drill-down queries
- evidence rows
- reasoning trace
- severity
- telemetry
- confidence score
- executive summary

Saved investigations are stored in workspace memory and exposed through:

```text
GET /investigations/latest
POST /workspace/{workspace_id}/investigations
GET /workspace/{workspace_id}/inspection
```

## Connectors

The connector boundary preserves existing SQLite workflows while adding production-ready PostgreSQL support.

Connector capabilities:

- typed connector configs
- connection validation
- health checks
- schema inspection
- read-only execution hooks
- connector telemetry
- PostgreSQL DSN redaction

Connector APIs:

```text
GET /connectors
GET /connectors/{connector_id}/health
GET /connectors/{connector_id}/schema
POST /connectors/validate
POST /connectors/{connector_id}/validate
```

SQLite remains the default local connector. PostgreSQL is enabled with `POSTGRES_URL`.

## Authentication and Workspace Persistence

The platform includes lightweight session authentication for local and hosted deployments.

Auth endpoints:

```text
POST /auth/login
POST /auth/logout
GET /auth/session
```

FastAPI accepts either:

```text
X-Session-Token: <token>
Authorization: Bearer <token>
```

Workspace persistence includes:

- saved SQL history
- saved investigations
- workflow transcripts
- semantic dataset memory
- telemetry summaries
- bookmarks
- recent activity
- active workspace sessions

Workspace APIs:

```text
GET /workspace/{workspace_id}
GET /workspace/{workspace_id}/inspection
GET /workspace/{workspace_id}/transcripts
GET /workspace/{workspace_id}/sql-history
POST /workspace/{workspace_id}/sql-history
POST /workspace/{workspace_id}/investigations
```

## Deployment Instructions

### Local Runtime

Required runtime:

- Python 3.11 or newer
- OpenAI API key
- SQLite database at `data/chinook.db`
- optional PostgreSQL database for connector validation

Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

Run Streamlit:

```powershell
python -m streamlit run app.py --server.port 8501
```

Run FastAPI:

```powershell
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

### Docker Compose

The repository includes Docker assets for frontend, backend, Redis, and PostgreSQL.

```powershell
docker compose up --build
```

The compose stack is intended for integrated validation of:

- Streamlit workspace
- FastAPI backend
- workflow runtime persistence
- PostgreSQL connector configuration
- Redis-compatible queue scaffolding

### Render Deployment

Deployment should set runtime environment variables in the hosting environment rather than committing secrets. The platform expects a Streamlit service for the workspace and can run the FastAPI backend as a separate service when API access is required.

## Environment Setup

Core environment variables:

| Variable | Purpose | Default |
| --- | --- | --- |
| `OPENAI_API_KEY` | OpenAI API access | required for model calls |
| `OPENAI_FALLBACK_MODEL` | fallback model after primary failures | unset |
| `OPENAI_TIMEOUT_SECONDS` | OpenAI request timeout | `30` |
| `OPENAI_MAX_ATTEMPTS` | OpenAI retry attempts | `2` |
| `OPENAI_TRUST_ENV` | allow proxy env vars for OpenAI client | `false` |
| `DATABASE_URL` | workspace/auth/report platform persistence URL | `sqlite:///data/platform_persistence.db` |
| `WORKFLOW_DATABASE_URL` | workflow runtime persistence URL | `sqlite:///data/workflow_runtime.db` |
| `POSTGRES_URL` | PostgreSQL connector DSN | unset |
| `POSTGRES_SCHEMA` | PostgreSQL schema to inspect | `public` |
| `POSTGRES_CONNECT_TIMEOUT_SECONDS` | PostgreSQL connection timeout | `5` |
| `AUTH_SESSION_PATH` | file-backed auth session store | `data/auth_sessions.json` |
| `AUTH_SESSION_TTL_HOURS` | session token lifetime | `12` |
| `AUTH_USERS` | JSON user map for local auth | unset |
| `AUTH_ADMIN_PASSWORD` | admin password override | `admin123` |
| `AUTH_ANALYST_PASSWORD` | analyst password override | `analyst123` |
| `AUTH_VIEWER_PASSWORD` | viewer password override | `viewer123` |

`AUTH_USERS` accepts a JSON object:

```json
{
  "ops.lead": {
    "password": "replace-me",
    "display_name": "Operations Lead",
    "team_id": "enterprise-ops",
    "role": "admin"
  }
}
```

Passwords can be provided as `password` for local development or `password_hash` for deployment. Password hashes use PBKDF2-SHA256 and can be generated with `backend.auth_sessions.hash_password`.

## Troubleshooting

### OpenAI Connection Errors

Check proxy variables and runtime diagnostics. The OpenAI client disables environment proxy trust by default.

```powershell
Get-ChildItem Env: | Where-Object { $_.Name -like '*PROXY*' }
```

Set `OPENAI_TRUST_ENV=true` only when the proxy path is intentionally required and validated.

### Authentication Failures

Confirm the configured user source:

- default local users
- `AUTH_USERS`
- `AUTH_ADMIN_PASSWORD`
- `AUTH_ANALYST_PASSWORD`
- `AUTH_VIEWER_PASSWORD`

Session tokens are stored in `AUTH_SESSION_PATH`. For ephemeral deployments, ensure the backing filesystem is writable or set a deployment-specific path.

### PostgreSQL Connector Unavailable

Check:

- `POSTGRES_URL`
- database network access
- username and password
- `POSTGRES_SCHEMA`
- SSL requirements through `POSTGRES_SSLMODE`

Validate through:

```text
GET /connectors/postgresql/health
GET /connectors/postgresql/schema
```

### Workspace Persistence Not Updating

Workspace memory is stored under `data/workspaces`. Confirm the deployment has write access to that directory. In read-only deployments, workspace memory will not persist across restarts.

### Runtime Diagnostics

FastAPI exposes:

```text
GET /health
GET /ready
GET /diagnostics
```

Streamlit exposes runtime status through the API and operations sections.

## Screenshots

Screenshots should be stored under `screenshots/` and referenced from portfolio or release notes.

Recommended capture set:

| Screenshot | Purpose |
| --- | --- |
| `screenshots/overview.png` | authenticated enterprise workspace |
| `screenshots/orchestration.png` | execution graph and lifecycle state |
| `screenshots/telemetry.png` | telemetry dashboard and exports |
| `screenshots/investigations.png` | autonomous investigation workspace |
| `screenshots/monitoring.png` | scheduled monitoring and executive briefing |
| `screenshots/api.png` | diagnostics and API surface |
| `screenshots/connectors.png` | connector health and schema inspection |

Screenshots should avoid secrets, raw API keys, private DSNs, and customer data.

## Technical Decisions

### Streamlit Remains the Workspace

Streamlit is retained because it supports fast iteration on operator workflows, telemetry views, charts, and investigation UX without replacing the backend control plane.

### FastAPI Owns the Control Plane

FastAPI provides stable, testable contracts for workflows, diagnostics, connectors, auth sessions, workspace persistence, telemetry, audit, governance, and reporting.

### SQLite Remains the Default Connector

SQLite keeps local development and portfolio validation deterministic. PostgreSQL support is added behind the connector abstraction without changing existing SQLite flows.

### LLM Access Is Isolated

`llm.py` centralizes OpenAI SDK calls, retries, fallback behavior, timeout settings, proxy handling, structured exceptions, and token/cost telemetry.

### Guardrails Are Deterministic

SQL validation is deterministic and fail-closed. Unsafe or malformed SQL does not reach execution.

### Workspace Persistence Is File-Backed for Now

File-backed workspace memory keeps deployment simple and testable. The structure is intentionally compatible with future migration to PostgreSQL or object storage.

### Authentication Is Lightweight

Session auth is deliberately minimal. It provides local login/logout and API session tokens without introducing a full identity provider. Production identity integration should move to SSO/OIDC.

## Validation

Production-quality changes should pass:

```powershell
python -m ruff check .
python -m pytest
python -m streamlit run app.py --server.headless true --server.port 8501
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

The current test suite covers orchestration lifecycle, telemetry schema, OpenAI runtime mocks, connector validation, governance controls, auth session persistence, workspace inspection, and API behavior.
