# PostgreSQL Persistence Guide

The platform now uses a durable persistence layer for workspace memory, auth sessions, saved reports, bookmarks, onboarding state, telemetry metadata, and orchestration history.

## Database Selection

Local development defaults to SQLite:

```bash
DATABASE_URL=sqlite:///data/platform_persistence.db
WORKFLOW_DATABASE_URL=sqlite:///data/workflow_runtime.db
```

Production should use PostgreSQL:

```bash
DATABASE_URL=postgresql://app_user:strong_password@postgres.example.com:5432/agentic_ai
```

`DATABASE_URL` controls platform persistence. When it is PostgreSQL, the backend orchestration storage factory also selects PostgreSQL repositories for workflow history, events, telemetry, agents, account metadata, and usage records.

## Stored Data

The durable platform database stores:

- workspace memory documents, including saved reports, bookmarks, pinned investigations, onboarding progress, preferences, query history, and recent activity
- auth users discovered from configured local auth metadata
- auth session tokens with expiry timestamps
- workflow orchestration history
- workflow events and telemetry
- agent execution records and coordination traces
- usage records

Workspace memory is intentionally stored as a JSON document with indexed workspace and team columns. This preserves compatibility with the existing Streamlit and FastAPI workspace model while moving durability out of local JSON files.

## Migrations

Schema initialization is lightweight and automatic at startup.

The migration bootstrap creates:

- `schema_migrations`
- `platform_users`
- `auth_sessions`
- `workspace_documents`
- `persistence_errors`
- workflow runtime tables
- account and usage tables

Current schema version: `1`.

Run a local validation manually:

```bash
python -c "from backend.persistence import validate_platform_database; print(validate_platform_database())"
```

## Startup Diagnostics

Startup validation now includes a `database` check. It reports:

- selected backend: `sqlite` or `postgresql`
- schema version
- connection latency
- degraded status if the database is unavailable

FastAPI diagnostics expose this through `/diagnostics`.

## Failure Handling

Workspace and auth persistence use durable repositories first. If the configured database is unavailable, workspace saves fall back to the prior local JSON path so local development remains recoverable. Startup diagnostics will report degraded persistence so operators can fix the database before relying on durable history.

For production, treat database startup warnings as release blockers.

## PostgreSQL Deployment Checklist

1. Provision PostgreSQL 14+.
2. Create a database and least-privilege application user.
3. Set `DATABASE_URL`.
4. Keep `WORKFLOW_DATABASE_URL` unset unless you intentionally want a separate SQLite workflow database.
5. Start FastAPI and check `/health`, `/ready`, and `/diagnostics`.
6. Run one workspace login, save a query/report, then confirm rows exist in `workspace_documents` and `auth_sessions`.
7. Run one backend workflow and confirm rows exist in `workflows`, `workflow_events`, and `workflow_telemetry`.

## Troubleshooting

- `psycopg is required`: install dependencies from `requirements.txt`.
- connection refused: verify host, port, firewall, and database service readiness.
- authentication failed: rotate the database password and update `DATABASE_URL`.
- schema missing: restart the app or run `validate_platform_database()` to bootstrap schema.
- data appears local-only: verify `DATABASE_URL` is set in both Streamlit and FastAPI environments.
