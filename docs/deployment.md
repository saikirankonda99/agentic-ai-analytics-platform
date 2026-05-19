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

## Local Production Stack

```bash
cp .env.example .env
docker compose up --build
```

Backend: `http://localhost:8000`  
Streamlit: `http://localhost:8501`

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
```

Production deployments should set `DATABASE_URL` to PostgreSQL:

```bash
DATABASE_URL=postgresql://app_user:password@postgres:5432/agentic_ai
```

Schema bootstrap is automatic and tracked in `schema_migrations`. See `docs/postgresql-persistence.md` for the detailed persistence guide.

## Health Checks

Container health checks probe application endpoints:

- backend: `GET /health`
- frontend: `GET /_stcore/health`

FastAPI also exposes:

- `GET /ready`
- `GET /readiness`
- `GET /diagnostics`

`/diagnostics` includes startup validation, auth posture, connector health, OpenAI runtime configuration, and execution policy.

## CI/CD

GitHub Actions runs lint, tests, startup probes, Docker build validation, and deployment-safety checks on pull requests and pushes to `main`. See `docs/cicd-runtime-validation.md` for the workflow contract.

## Future Worker Paths

The current runtime uses FastAPI background tasks. The queue abstractions are intentionally compatible with later Celery/RQ adoption for:

- workflow execution workers
- autonomous monitoring jobs
- investigation workers
- executive briefing generation

Redis pub/sub is scaffolded for websocket scaling across multiple backend instances.
