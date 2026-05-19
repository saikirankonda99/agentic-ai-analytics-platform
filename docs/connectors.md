# Connector Platform

The connector layer provides a typed boundary between orchestration code and physical data systems. SQLite remains the default local analytics connector, while PostgreSQL can be enabled through `POSTGRES_URL`.

## Connector Model

`backend.connectors` defines:

- typed connector configuration models for SQLite and PostgreSQL
- connection validation
- health checks with connector telemetry
- schema inspection
- read-only query execution hooks
- public configuration serialization with PostgreSQL DSN redaction

The existing `db.py` functions still expose `get_schema()` and `run_query()` for Streamlit and workflow compatibility, but those calls now route through the SQLite connector.

## Configuration

SQLite:

- `SQLITE_DATABASE_PATH`, defaults to `data/chinook.db`

PostgreSQL:

- `POSTGRES_URL`
- `POSTGRES_SCHEMA`, defaults to `public`
- `POSTGRES_CONNECT_TIMEOUT_SECONDS`, defaults to `5`
- `POSTGRES_SSLMODE`, optional

## API

FastAPI exposes:

- `GET /connectors`
- `GET /connectors/{connector_id}/health`
- `GET /connectors/{connector_id}/schema`
- `POST /connectors/validate`
- `POST /connectors/{connector_id}/validate`

Connector responses include status, latency, timestamp, message, and telemetry metadata. PostgreSQL schema inspection returns tables and columns from `information_schema.columns` for the configured schema.

## Streamlit Diagnostics

The Streamlit `API` workspace includes a connector diagnostics panel. It displays:

- configured connectors
- connector kind and enabled state
- startup validation status
- validation latency
- safe configuration posture
- PostgreSQL configured state and schema name
- SQLite database path

The panel intentionally redacts PostgreSQL credentials and does not display raw DSNs.

## Startup Validation

FastAPI runtime diagnostics include connector startup posture through `GET /diagnostics`. The diagnostics payload validates connector health and reports safe configuration metadata without exposing secrets.

PostgreSQL health checks only attempt a network connection when `POSTGRES_URL` is configured. Without `POSTGRES_URL`, PostgreSQL reports `not_configured` rather than failing application startup.

## Production Direction

The current PostgreSQL support validates connectivity and inspects schema metadata without changing the default SQLite workflow. The next production step is connector-scoped governance enforcement, query routing by workspace policy, durable connector telemetry history, and credential management through a secrets provider rather than process environment variables.
