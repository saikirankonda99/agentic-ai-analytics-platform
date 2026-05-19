# CI/CD and Runtime Validation

The platform uses GitHub Actions to enforce deployment safety before changes reach production branches. The pipeline validates code quality, runtime initialization, application startup, and Docker build integrity.

## Workflow Structure

`.github/workflows/ci.yml` defines modular jobs:

- `lint`: installs dependencies with pip caching and runs `ruff`.
- `test`: runs the full pytest suite and uploads pytest cache diagnostics on failure.
- `startup`: runs backend startup validation, probes FastAPI health/diagnostics, and verifies Streamlit startup through the health endpoint.
- `docker`: builds backend and frontend images with Docker Buildx cache.
- `deployment-safety`: verifies deployment-critical files and baseline environment examples.

The workflow runs on pull requests and pushes to `main`.

## Startup Validation

`backend.startup` provides a shared startup validation boundary used by FastAPI, Docker entrypoints, tests, and CI.

Validated systems:

- environment configuration
- OpenAI runtime posture
- connector registry and required SQLite connector
- authentication configuration
- telemetry schema initialization
- orchestration runtime initialization

Strict startup behavior is controlled through:

```text
STARTUP_VALIDATION_STRICT=true
```

In non-strict mode, missing optional services such as OpenAI credentials or PostgreSQL configuration are reported as warnings instead of preventing local startup.

## Runtime Diagnostics

FastAPI exposes:

```text
GET /health
GET /ready
GET /readiness
GET /diagnostics
```

`/diagnostics` includes startup validation, auth posture, connector diagnostics, OpenAI runtime configuration, execution policy, and environment configuration status.

## Docker Reliability

Dockerfiles run as a non-root application user, create writable runtime data directories, run startup validation before service launch, and expose container health checks.

Backend:

```text
Dockerfile.backend
```

Frontend:

```text
Dockerfile.frontend
```

The root `Dockerfile` remains a Streamlit-compatible single-service deployment target.

## Failure Diagnostics

CI captures Streamlit startup logs when the startup probe fails. FastAPI startup validation logs structured JSON through the platform logging layer. Docker health checks exercise HTTP health endpoints rather than relying only on process liveness.
