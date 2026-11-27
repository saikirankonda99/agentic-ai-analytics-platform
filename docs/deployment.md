# Distributed Deployment Notes

This repository now separates local app behavior from production-oriented orchestration boundaries.

## Services

- `backend`: FastAPI orchestration API, REST/SSE/websocket endpoints.
- `frontend`: Streamlit UI, unchanged runtime entrypoint.
- `postgres`: PostgreSQL database for durable workspace, auth, report, telemetry, and workflow persistence.
- `redis`: Pub/sub and queue coordination foundation for websocket fanout and workers.

## Runtime Boundaries

- `backend.config` centralizes environment-driven settings.
- `backend.persistence` owns platform persistence, schema bootstrap, auth sessions, and workspace documents.
- `backend.storage` owns workflow, event, telemetry, usage, account, and agent metadata repositories.
- `backend.memory` defines vector-memory and embedding interfaces, with pgvector scaffolding.
- `backend.messaging` defines Redis-ready event propagation.
- `backend.workers` defines Redis-ready distributed worker queue abstractions.
- `backend.runtime` remains the orchestration execution boundary.

## Local Container Stack

```bash
cp .env.example .env
# Configure AUTH_USERS as described below before starting production-mode services.
docker compose up --build
```

Backend: `http://localhost:8000`  
Streamlit: `http://localhost:8501`

This stack is a development integration setup. PostgreSQL and Redis in this Compose file use local defaults; operating a customer deployment still requires infrastructure configuration, customer data isolation, and deployment testing. The current API execution endpoint simulates workflow stages. Redis workers and pgvector retrieval are not implemented.

## Explicit production users

Both services use `APP_ENV=production` in Compose. This mode disables the built-in demo accounts. Missing, malformed, or unhashed `AUTH_USERS` credentials fail startup validation.

Generate a password hash locally without putting the password in shell history:

```bash
python -c 'from getpass import getpass; from backend.auth_sessions import hash_password; print(hash_password(getpass("Password: ")))'
```

Copy the resulting hash into an `AUTH_USERS` JSON object in your private `.env` file. Replace the placeholder below; do not commit the file:

```dotenv
APP_ENV=production
AUTH_USERS='{"owner":{"password_hash":"PASTE_GENERATED_HASH_HERE","display_name":"Business Owner","team_id":"demo-business","role":"admin"}}'
```

Roles are `admin`, `analyst`, or `viewer`. User, team, and role come from the authenticated session. The Streamlit sidebar displays these values; changing a client header cannot grant another user's access. This authorization does not yet provide separate database connectors and retrieval histories for different customers.

Use `POST /auth/login` to obtain a session token. Private routes accept `X-Session-Token` or `Authorization: Bearer <token>`. Diagnostics and connector endpoints require an admin. Workflow reads, streams, and workspace APIs also enforce ownership and write roles. Public health/readiness responses expose only service status. Endpoints that formerly exposed a global latest investigation now return an unavailable response until an explicit owned workflow is supplied where supported.

## Startup Validation

Both Docker service entrypoints run startup validation before launching the application process. Validation covers environment configuration, OpenAI runtime posture, connector registration, auth configuration, telemetry initialization, and orchestration initialization.

Set strict startup validation when a deployment should fail fast on required runtime errors:

```bash
STARTUP_VALIDATION_STRICT=true
```

Optional dependencies such as `OPENAI_API_KEY` and `POSTGRES_URL` report warnings in non-strict local deployments.

## Persistence

Local development uses SQLite by default:

```bash
DATABASE_URL=sqlite:///data/platform_persistence.db
WORKFLOW_DATABASE_URL=sqlite:///data/workflow_runtime.db
```

Production deployments should set both persistence URLs to PostgreSQL:

```bash
DATABASE_URL=postgresql://app_user:password@postgres:5432/agentic_ai
WORKFLOW_DATABASE_URL=postgresql://app_user:password@postgres:5432/agentic_ai
```

`DATABASE_URL` owns workspace/auth/report persistence. `WORKFLOW_DATABASE_URL` owns workflow history, events, telemetry, agents, and usage persistence. If `WORKFLOW_DATABASE_URL` is omitted, the runtime falls back to `DATABASE_URL` for compatibility and reports that fallback in startup diagnostics.

Schema bootstrap is automatic and tracked in `schema_migrations`. See `docs/postgresql-persistence.md` for the detailed persistence guide.

## Health Checks

Container health checks probe application endpoints:

- backend: `GET /health`
- frontend: `GET /_stcore/health`

FastAPI also exposes:

- `GET /ready`
- `GET /readiness`
- `GET /diagnostics`

`/diagnostics` requires an admin session and includes startup validation, auth posture, connector health, OpenAI runtime configuration, and execution policy.

## CI/CD

GitHub Actions runs lint, tests, startup probes, Docker build validation, and deployment-safety checks on pull requests and pushes to `main`. See `docs/cicd-runtime-validation.md` for the workflow contract.

## Future Worker Paths

The current runtime uses FastAPI background tasks. The queue abstractions are intentionally compatible with later Celery/RQ adoption for:

- workflow execution workers
- autonomous monitoring jobs
- investigation workers
- executive briefing generation

Redis pub/sub is scaffolded for websocket scaling across multiple backend instances.
