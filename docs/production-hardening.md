# Production Hardening Notes

This backend keeps the current Streamlit-compatible runtime while adding operational guardrails around the orchestration surface.

## Configuration

Runtime settings live in `backend.config.AppSettings` and are read from environment variables. The service remains usable without Redis, Postgres, or pgvector configured.

## Observability

`backend.logging` configures JSON structured logs. The orchestration runtime logs:

- workflow submission
- workflow start/completion
- failure-state transitions
- readiness check failures

## Health Checks

- `GET /health`: liveness check for load balancers.
- `GET /ready`: lightweight dependency readiness for workflow storage, event storage, telemetry, agent metadata, traces, and vector memory.

## Testing

The test suite covers:

- workflow API execution and retrieval
- health/readiness endpoints
- orchestration lifecycle and telemetry generation
- repository persistence boundaries

## CI

GitHub Actions runs:

- `ruff check backend tests`
- `black --check backend tests`
- `pytest`

## Failure Handling

Runtime failures are logged and then moved into the workflow `failed` lifecycle state when possible. If failure-state persistence itself fails, the runtime logs the secondary failure and re-raises for visibility.
