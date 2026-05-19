from __future__ import annotations

import sys
from types import SimpleNamespace

from fastapi.testclient import TestClient

from backend.connectors import (
    ConnectorRegistry,
    PostgresConnector,
    PostgresConnectorConfig,
    SQLiteConnector,
    SQLiteConnectorConfig,
)
from backend.main import app


def test_sqlite_connector_validates_and_inspects_schema() -> None:
    connector = SQLiteConnector(SQLiteConnectorConfig(database_path="data/chinook.db"))

    health = connector.validate_connection()
    schema = connector.inspect_schema()

    assert health.status == "healthy"
    assert health.telemetry.operation == "connection_validation"
    assert schema["table_count"] > 0
    assert "Table:" in schema["schema_text"]
    assert schema["telemetry"]["operation"] == "schema_inspection"


def test_sqlite_connector_reports_unavailable_for_missing_database() -> None:
    connector = SQLiteConnector(SQLiteConnectorConfig(database_path="data/does-not-exist/missing.db"))

    health = connector.health_check()

    assert health.status == "unavailable"
    assert health.telemetry.status == "unavailable"
    assert "SQLite validation failed" in health.message


def test_postgres_connector_reports_not_configured_without_network() -> None:
    connector = PostgresConnector(PostgresConnectorConfig(dsn=None))

    health = connector.validate_connection()
    schema = connector.inspect_schema()

    assert health.status == "not_configured"
    assert "POSTGRES_URL" in health.message
    assert schema["table_count"] == 0
    assert schema["health"]["status"] == "not_configured"


def test_postgres_connector_validates_with_psycopg_connection(monkeypatch) -> None:
    class FakeCursor:
        def __enter__(self) -> "FakeCursor":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def execute(self, sql: str, params: tuple[object, ...] | None = None) -> None:
            self.sql = sql
            self.params = params

        def fetchone(self) -> tuple[int]:
            return (1,)

    class FakeConnection:
        def __enter__(self) -> "FakeConnection":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def cursor(self) -> FakeCursor:
            return FakeCursor()

    calls: list[dict[str, object]] = []

    def connect(dsn: str, **kwargs: object) -> FakeConnection:
        calls.append({"dsn": dsn, **kwargs})
        return FakeConnection()

    monkeypatch.setitem(sys.modules, "psycopg", SimpleNamespace(connect=connect))
    connector = PostgresConnector(PostgresConnectorConfig(dsn="postgresql://user:pass@localhost:5432/app"))

    health = connector.validate_connection()

    assert health.status == "healthy"
    assert calls[0]["dsn"] == "postgresql://user:pass@localhost:5432/app"
    assert calls[0]["connect_timeout"] == 5


def test_postgres_connector_inspects_schema_with_psycopg_connection(monkeypatch) -> None:
    class FakeDescription:
        def __init__(self, name: str) -> None:
            self.name = name

    class FakeCursor:
        description = [FakeDescription("id")]

        def __enter__(self) -> "FakeCursor":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def execute(self, sql: str, params: tuple[object, ...] | None = None) -> None:
            self.sql = sql
            self.params = params

        def fetchone(self) -> tuple[int]:
            return (1,)

        def fetchall(self) -> list[tuple[str, str, str, str, str]]:
            return [
                ("analytics", "customers", "id", "integer", "NO"),
                ("analytics", "customers", "email", "text", "YES"),
            ]

    class FakeConnection:
        def __enter__(self) -> "FakeConnection":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def cursor(self) -> FakeCursor:
            return FakeCursor()

    monkeypatch.setitem(sys.modules, "psycopg", SimpleNamespace(connect=lambda *args, **kwargs: FakeConnection()))
    connector = PostgresConnector(
        PostgresConnectorConfig(dsn="postgresql://user:pass@localhost:5432/app", schema="analytics")
    )

    schema = connector.inspect_schema()

    assert schema["table_count"] == 1
    assert schema["tables"][0]["name"] == "customers"
    assert schema["tables"][0]["columns"][0]["nullable"] is False
    assert schema["telemetry"]["operation"] == "schema_inspection"


def test_connector_registry_redacts_postgres_dsn() -> None:
    registry = ConnectorRegistry(
        {
            "sqlite": SQLiteConnector(SQLiteConnectorConfig(database_path="data/chinook.db")),
            "postgresql": PostgresConnector(
                PostgresConnectorConfig(dsn="postgresql://analytics:secret@localhost:5432/analytics")
            ),
        }
    )

    postgres = next(item for item in registry.list_connectors() if item["connector_id"] == "postgresql")

    assert postgres["configured"] is True
    assert "secret" not in postgres["dsn"]
    assert postgres["dsn"] == "postgresql://***:***@localhost:5432/analytics"


def test_connector_registry_diagnostics_include_safe_environment() -> None:
    registry = ConnectorRegistry({"sqlite": SQLiteConnector(SQLiteConnectorConfig(database_path="data/chinook.db"))})

    diagnostics = registry.diagnostics(validate=True)

    assert diagnostics["connector_count"] == 1
    assert diagnostics["health"]["sqlite"]["status"] == "healthy"
    assert "postgres_configured" in diagnostics["configuration"]


def test_connector_api_endpoints() -> None:
    client = TestClient(app)

    connectors = client.get("/connectors").json()
    sqlite_health = client.get("/connectors/sqlite/health").json()
    sqlite_schema = client.get("/connectors/sqlite/schema").json()
    validation = client.post("/connectors/validate", json={"connector_id": "sqlite"}).json()
    missing = client.get("/connectors/does-not-exist/health")

    assert any(item["connector_id"] == "sqlite" for item in connectors["connectors"])
    assert sqlite_health["status"] == "healthy"
    assert sqlite_schema["table_count"] > 0
    assert validation["status"] == "healthy"
    assert missing.status_code == 404
