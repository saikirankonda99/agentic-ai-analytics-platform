from __future__ import annotations

import os
import json
import sqlite3
import time
from contextlib import closing
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Protocol

from backend.config import settings
from guardrails import is_safe_sql


ConnectorKind = Literal["sqlite", "postgresql"]
ConnectorStatus = Literal["healthy", "degraded", "unavailable", "not_configured"]


@dataclass(frozen=True)
class ConnectorConfig:
    connector_id: str
    kind: ConnectorKind
    name: str
    enabled: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)
    organization_id: str | None = None
    workspace_ids: tuple[str, ...] = ()
    public_demo: bool = False

    def public_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SQLiteConnectorConfig(ConnectorConfig):
    database_path: str = "data/chinook.db"

    def __init__(
        self,
        connector_id: str = "sqlite",
        name: str = "Local Chinook SQLite",
        database_path: str = "data/chinook.db",
        enabled: bool = True,
        metadata: dict[str, Any] | None = None,
        organization_id: str | None = None,
        workspace_ids: tuple[str, ...] = (),
        public_demo: bool | None = None,
    ) -> None:
        object.__setattr__(self, "connector_id", connector_id)
        object.__setattr__(self, "kind", "sqlite")
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "enabled", enabled)
        object.__setattr__(self, "metadata", metadata or {})
        object.__setattr__(self, "database_path", database_path)
        object.__setattr__(self, "organization_id", organization_id)
        object.__setattr__(self, "workspace_ids", tuple(workspace_ids))
        object.__setattr__(self, "public_demo", _is_bundled_database(database_path) if public_demo is None else public_demo)


@dataclass(frozen=True)
class PostgresConnectorConfig(ConnectorConfig):
    dsn: str | None = None
    schema: str = "public"
    connect_timeout_seconds: int = 5
    sslmode: str | None = None

    def __init__(
        self,
        connector_id: str = "postgresql",
        name: str = "PostgreSQL Analytics Warehouse",
        dsn: str | None = None,
        schema: str = "public",
        connect_timeout_seconds: int = 5,
        sslmode: str | None = None,
        enabled: bool = True,
        metadata: dict[str, Any] | None = None,
        organization_id: str | None = None,
        workspace_ids: tuple[str, ...] = (),
    ) -> None:
        object.__setattr__(self, "connector_id", connector_id)
        object.__setattr__(self, "kind", "postgresql")
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "enabled", enabled)
        object.__setattr__(self, "metadata", metadata or {})
        object.__setattr__(self, "dsn", dsn)
        object.__setattr__(self, "schema", schema)
        object.__setattr__(self, "connect_timeout_seconds", connect_timeout_seconds)
        object.__setattr__(self, "sslmode", sslmode)
        object.__setattr__(self, "organization_id", organization_id)
        object.__setattr__(self, "workspace_ids", tuple(workspace_ids))
        object.__setattr__(self, "public_demo", False)

    def public_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        dsn = self.dsn or ""
        payload["configured"] = bool(dsn)
        payload["dsn"] = _redact_dsn(dsn) if dsn else None
        return payload


@dataclass(frozen=True)
class ConnectorTelemetryEvent:
    connector_id: str
    operation: str
    status: ConnectorStatus
    latency_ms: int
    timestamp: str
    message: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ConnectorHealth:
    connector_id: str
    kind: ConnectorKind
    status: ConnectorStatus
    latency_ms: int
    checked_at: str
    message: str
    telemetry: ConnectorTelemetryEvent
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["telemetry"] = self.telemetry.as_dict()
        return payload


class DataConnector(Protocol):
    config: ConnectorConfig

    def validate_connection(self) -> ConnectorHealth:
        """Validate that the connector can answer a lightweight query."""

    def health_check(self) -> ConnectorHealth:
        """Return connector health with telemetry."""

    def inspect_schema(self) -> dict[str, Any]:
        """Inspect connector schema and return formatted schema metadata."""

    def execute_read(self, sql: str) -> tuple[list[str], list[Any]]:
        """Execute a read-only query through the connector."""


class SQLiteConnector:
    def __init__(self, config: SQLiteConnectorConfig) -> None:
        self.config = config

    @property
    def database_path(self) -> Path:
        path = Path(self.config.database_path)
        if not path.is_absolute():
            path = Path(__file__).resolve().parent.parent / path
        return path

    def validate_connection(self) -> ConnectorHealth:
        started = time.perf_counter()
        try:
            with closing(self._connect_read_only()) as connection:
                connection.execute("SELECT 1").fetchone()
            return _health(self.config, "healthy", started, "SQLite connector validated.")
        except Exception as exc:
            return _health(self.config, "unavailable", started, f"SQLite validation failed: {exc}")

    def health_check(self) -> ConnectorHealth:
        return self.validate_connection()

    def inspect_schema(self) -> dict[str, Any]:
        started = time.perf_counter()
        with closing(self._connect_read_only()) as connection:
            cursor = connection.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
            table_names = [row[0] for row in cursor.fetchall()]
            tables = []
            formatted = []
            for table_name in table_names:
                quoted_name = table_name.replace('"', '""')
                cursor.execute(f'PRAGMA table_info("{quoted_name}");')
                columns = [
                    {"name": row[1], "type": row[2], "nullable": not bool(row[3]), "primary_key": bool(row[5])}
                    for row in cursor.fetchall()
                ]
                tables.append({"name": table_name, "schema": "main", "columns": columns})
                formatted.append(f"Table: {table_name}\n" + ", ".join(f"{column['name']} ({column['type']})" for column in columns))
        latency_ms = int((time.perf_counter() - started) * 1000)
        return {
            "connector_id": self.config.connector_id,
            "kind": self.config.kind,
            "schema": "main",
            "table_count": len(tables),
            "tables": tables,
            "schema_text": "\n\n".join(formatted),
            "telemetry": _telemetry(self.config.connector_id, "schema_inspection", "healthy", latency_ms, "SQLite schema inspected.").as_dict(),
        }

    def execute_read(self, sql: str) -> tuple[list[str], list[Any]]:
        _require_read_query(sql)
        max_rows = _safe_int(os.getenv("SQL_MAX_ROWS"), 10_000)
        timeout_seconds = _safe_int(os.getenv("SQL_QUERY_TIMEOUT_SECONDS"), 10)
        deadline = time.monotonic() + timeout_seconds
        with closing(self._connect_read_only()) as connection:
            connection.set_authorizer(_sqlite_read_authorizer)
            connection.set_progress_handler(lambda: int(time.monotonic() > deadline), 1000)
            cursor = connection.cursor()
            cursor.execute(sql)
            rows = cursor.fetchmany(max_rows + 1)
            if len(rows) > max_rows:
                raise ValueError(f"Query exceeded the {max_rows} row limit; add a narrower filter or LIMIT.")
            columns = [description[0] for description in cursor.description or []]
        return columns, rows

    def _connect_read_only(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path.resolve().as_uri() + "?mode=ro", uri=True)
        connection.execute("PRAGMA query_only=ON")
        return connection


class PostgresConnector:
    def __init__(self, config: PostgresConnectorConfig) -> None:
        self.config = config

    def validate_connection(self) -> ConnectorHealth:
        started = time.perf_counter()
        if not self.config.dsn:
            return _health(self.config, "not_configured", started, "POSTGRES_URL is not configured.")
        try:
            with self._connect() as connection:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT 1")
                    cursor.fetchone()
            return _health(self.config, "healthy", started, "PostgreSQL connector validated.")
        except Exception as exc:
            return _health(self.config, "unavailable", started, f"PostgreSQL validation failed: {type(exc).__name__}.")

    def health_check(self) -> ConnectorHealth:
        return self.validate_connection()

    def inspect_schema(self) -> dict[str, Any]:
        started = time.perf_counter()
        health = self.validate_connection()
        if health.status != "healthy":
            return {
                "connector_id": self.config.connector_id,
                "kind": self.config.kind,
                "schema": self.config.schema,
                "table_count": 0,
                "tables": [],
                "schema_text": "",
                "health": health.as_dict(),
                "telemetry": health.telemetry.as_dict(),
            }
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT table_schema, table_name, column_name, data_type, is_nullable
                    FROM information_schema.columns
                    WHERE table_schema = %s
                    ORDER BY table_schema, table_name, ordinal_position
                    """,
                    (self.config.schema,),
                )
                rows = cursor.fetchall()
        tables_by_name: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for table_schema, table_name, column_name, data_type, is_nullable in rows:
            tables_by_name.setdefault((table_schema, table_name), []).append(
                {"name": column_name, "type": data_type, "nullable": is_nullable == "YES", "primary_key": False}
            )
        tables = [
            {"schema": table_schema, "name": table_name, "columns": columns}
            for (table_schema, table_name), columns in tables_by_name.items()
        ]
        formatted = [
            f"Table: {table['schema']}.{table['name']}\n"
            + ", ".join(f"{column['name']} ({column['type']})" for column in table["columns"])
            for table in tables
        ]
        latency_ms = int((time.perf_counter() - started) * 1000)
        return {
            "connector_id": self.config.connector_id,
            "kind": self.config.kind,
            "schema": self.config.schema,
            "table_count": len(tables),
            "tables": tables,
            "schema_text": "\n\n".join(formatted),
            "health": health.as_dict(),
            "telemetry": _telemetry(
                self.config.connector_id,
                "schema_inspection",
                "healthy",
                latency_ms,
                "PostgreSQL schema inspected.",
                {"schema": self.config.schema, "table_count": len(tables)},
            ).as_dict(),
        }

    def execute_read(self, sql: str) -> tuple[list[str], list[Any]]:
        _require_read_query(sql)
        max_rows = _safe_int(os.getenv("SQL_MAX_ROWS"), 10_000)
        timeout_ms = _safe_int(os.getenv("SQL_QUERY_TIMEOUT_SECONDS"), 10) * 1000
        with self._connect() as connection:
            connection.read_only = True
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('statement_timeout', %s, true)", (str(timeout_ms),))
                cursor.execute(sql)
                rows = cursor.fetchmany(max_rows + 1)
                if len(rows) > max_rows:
                    raise ValueError(f"Query exceeded the {max_rows} row limit; add a narrower filter or LIMIT.")
                columns = [description.name for description in cursor.description or []]
        return columns, rows

    def _connect(self) -> Any:
        try:
            import psycopg
        except ImportError as exc:  # pragma: no cover - dependency is declared in requirements
            raise RuntimeError("psycopg is required for PostgreSQL connectors.") from exc
        kwargs: dict[str, Any] = {"connect_timeout": self.config.connect_timeout_seconds}
        if self.config.sslmode:
            kwargs["sslmode"] = self.config.sslmode
        return psycopg.connect(self.config.dsn, **kwargs)


class ConnectorRegistry:
    def __init__(self, connectors: dict[str, DataConnector] | None = None) -> None:
        self._connectors = default_connectors() if connectors is None else connectors

    def list_connectors(self) -> list[dict[str, Any]]:
        return [connector.config.public_dict() for connector in self._connectors.values()]

    def get(self, connector_id: str = "sqlite") -> DataConnector:
        """Administrative configuration access; customer execution must use get_for_workspace."""
        try:
            return self._connectors[connector_id]
        except KeyError as exc:
            raise ValueError(f"Unknown connector: {connector_id}") from exc

    def get_for_workspace(
        self, connector_id: str, *, organization_id: str, workspace_id: str,
    ) -> DataConnector:
        """Resolve a server-configured grant, never a caller-supplied DSN or tenant label."""
        if not organization_id or not workspace_id:
            raise PermissionError("An authenticated organization and workspace are required.")
        connector = self.get(connector_id)
        if not connector.config.enabled:
            raise PermissionError("This connector is disabled.")
        if _is_public_demo_connector(connector):
            return connector
        config = connector.config
        if config.organization_id != organization_id or workspace_id not in config.workspace_ids:
            raise PermissionError("This workspace is not authorized for the connector.")
        return connector

    def get_public_demo(self, connector_id: str = "sqlite") -> DataConnector:
        connector = self.get(connector_id)
        if not connector.config.enabled or not _is_public_demo_connector(connector):
            raise PermissionError("Unscoped queries are restricted to the bundled example database.")
        return connector

    def list_for_workspace(self, *, organization_id: str, workspace_id: str) -> list[dict[str, Any]]:
        if not organization_id or not workspace_id:
            raise PermissionError("An authenticated organization and workspace are required.")
        visible = []
        for connector_id in self._connectors:
            try:
                connector = self.get_for_workspace(
                    connector_id, organization_id=organization_id, workspace_id=workspace_id,
                )
            except PermissionError:
                continue
            visible.append(connector.config.public_dict())
        return visible

    def diagnostics_for_workspace(
        self, *, organization_id: str, workspace_id: str, validate: bool = True,
    ) -> dict[str, Any]:
        connectors = self.list_for_workspace(organization_id=organization_id, workspace_id=workspace_id)
        health = {}
        if validate:
            for item in connectors:
                connector = self.get_for_workspace(
                    item["connector_id"], organization_id=organization_id, workspace_id=workspace_id,
                )
                health[item["connector_id"]] = connector.health_check().as_dict()
        return {
            "connector_count": len(connectors), "connectors": connectors, "health": health,
            "configuration": {
                "scope": "workspace",
                "postgres_configured": any(item["kind"] == "postgresql" for item in connectors),
                "postgres_schema": ", ".join(item["schema"] for item in connectors if item["kind"] == "postgresql"),
                "sqlite_database_path": ", ".join(item["database_path"] for item in connectors if item["kind"] == "sqlite"),
            },
        }

    def validate(self, connector_id: str) -> dict[str, Any]:
        return self.get(connector_id).validate_connection().as_dict()

    def health(self, connector_id: str) -> dict[str, Any]:
        return self.get(connector_id).health_check().as_dict()

    def inspect_schema(self, connector_id: str) -> dict[str, Any]:
        return self.get(connector_id).inspect_schema()

    def diagnostics(self, *, validate: bool = True) -> dict[str, Any]:
        connectors = self.list_connectors()
        health: dict[str, Any] = {}
        if validate:
            for connector in connectors:
                connector_id = connector["connector_id"]
                health[connector_id] = self.health(connector_id)
        return {
            "connector_count": len(connectors),
            "connectors": connectors,
            "health": health,
            "configuration": connector_environment_diagnostics(),
        }


def default_connectors() -> dict[str, DataConnector]:
    sqlite_path = os.getenv("SQLITE_DATABASE_PATH", "data/chinook.db")
    postgres_schema = os.getenv("POSTGRES_SCHEMA", "public")
    postgres_timeout = _safe_int(os.getenv("POSTGRES_CONNECT_TIMEOUT_SECONDS"), 5)
    postgres_sslmode = os.getenv("POSTGRES_SSLMODE")
    connectors: dict[str, DataConnector] = {
        "sqlite": SQLiteConnector(SQLiteConnectorConfig(
            database_path=sqlite_path,
            organization_id=os.getenv("SQLITE_ORGANIZATION_ID"),
            workspace_ids=_workspace_ids(os.getenv("SQLITE_WORKSPACE_IDS", "[]")),
        )),
        "postgresql": PostgresConnector(
            PostgresConnectorConfig(
                dsn=settings.postgres_url or os.getenv("POSTGRES_URL"),
                schema=postgres_schema,
                connect_timeout_seconds=postgres_timeout,
                sslmode=postgres_sslmode,
                enabled=bool(settings.postgres_url or os.getenv("POSTGRES_URL")),
                organization_id=os.getenv("POSTGRES_ORGANIZATION_ID"),
                workspace_ids=_workspace_ids(os.getenv("POSTGRES_WORKSPACE_IDS", "[]")),
            )
        ),
    }
    # Only server configuration can add private connectors. Connection credentials
    # are referenced through environment variable names, never supplied by API clients.
    configured = os.getenv("ANALYTICS_CONNECTORS_JSON", "[]")
    try:
        definitions = json.loads(configured)
        if not isinstance(definitions, list):
            raise ValueError
        for definition in definitions:
            if not isinstance(definition, dict):
                raise ValueError
            connector_id = definition["connector_id"]
            owner = definition["organization_id"]
            workspaces = _workspace_ids(definition["workspace_ids"])
            if not isinstance(connector_id, str) or not connector_id or connector_id in connectors:
                raise ValueError
            if not isinstance(owner, str) or not owner or not workspaces:
                raise ValueError
            common = {"connector_id": connector_id, "name": definition.get("name", connector_id),
                      "organization_id": owner, "workspace_ids": workspaces}
            if definition["kind"] == "sqlite":
                connectors[connector_id] = SQLiteConnector(SQLiteConnectorConfig(
                    **common, database_path=definition["database_path"], public_demo=False,
                ))
            elif definition["kind"] == "postgresql":
                dsn_env = definition["dsn_env"]
                if not isinstance(dsn_env, str) or not dsn_env:
                    raise ValueError
                dsn = os.getenv(dsn_env)
                connectors[connector_id] = PostgresConnector(PostgresConnectorConfig(
                    **common, dsn=dsn, schema=definition.get("schema", "public"), enabled=bool(dsn),
                ))
            else:
                raise ValueError
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Invalid server analytics connector configuration.") from exc
    return connectors


def get_connector_registry() -> ConnectorRegistry:
    return connector_registry


def connector_environment_diagnostics() -> dict[str, Any]:
    postgres_url = settings.postgres_url or os.getenv("POSTGRES_URL")
    return {
        "sqlite_database_path": os.getenv("SQLITE_DATABASE_PATH", "data/chinook.db"),
        "postgres_configured": bool(postgres_url),
        "postgres_url": _redact_dsn(postgres_url) if postgres_url else None,
        "postgres_schema": os.getenv("POSTGRES_SCHEMA", "public"),
        "postgres_connect_timeout_seconds": _safe_int(os.getenv("POSTGRES_CONNECT_TIMEOUT_SECONDS"), 5),
        "postgres_sslmode_configured": bool(os.getenv("POSTGRES_SSLMODE")),
    }


def _health(
    config: ConnectorConfig,
    status: ConnectorStatus,
    started: float,
    message: str,
    metadata: dict[str, Any] | None = None,
) -> ConnectorHealth:
    latency_ms = int((time.perf_counter() - started) * 1000)
    telemetry = _telemetry(config.connector_id, "connection_validation", status, latency_ms, message, metadata)
    return ConnectorHealth(
        connector_id=config.connector_id,
        kind=config.kind,
        status=status,
        latency_ms=latency_ms,
        checked_at=telemetry.timestamp,
        message=message,
        telemetry=telemetry,
        metadata=metadata or {},
    )


def _telemetry(
    connector_id: str,
    operation: str,
    status: ConnectorStatus,
    latency_ms: int,
    message: str,
    metadata: dict[str, Any] | None = None,
) -> ConnectorTelemetryEvent:
    return ConnectorTelemetryEvent(
        connector_id=connector_id,
        operation=operation,
        status=status,
        latency_ms=latency_ms,
        timestamp=datetime.now(timezone.utc).isoformat(),
        message=message,
        metadata=metadata or {},
    )


def _redact_dsn(dsn: str) -> str:
    if "@" not in dsn or "://" not in dsn:
        return "[configured]"
    prefix, suffix = dsn.rsplit("@", 1)
    scheme = prefix.split("://", 1)[0] if "://" in prefix else "postgresql"
    return f"{scheme}://***:***@{suffix.split('?', 1)[0].split('#', 1)[0]}"


def _workspace_ids(value: str | list[str] | tuple[str, ...]) -> tuple[str, ...]:
    try:
        items = json.loads(value) if isinstance(value, str) else value
    except (TypeError, ValueError) as exc:
        raise ValueError("Workspace grants must be a JSON array of workspace IDs.") from exc
    if not isinstance(items, (list, tuple)) or any(not isinstance(item, str) or not item.strip() for item in items):
        raise ValueError("Workspace grants must be a JSON array of workspace IDs.")
    return tuple(items)


def _is_bundled_database(database_path: str) -> bool:
    project = Path(__file__).resolve().parent.parent
    path = Path(database_path)
    if not path.is_absolute():
        path = project / path
    return path.resolve() == (project / "data" / "chinook.db").resolve()


def _is_public_demo_connector(connector: DataConnector) -> bool:
    return (
        isinstance(connector, SQLiteConnector)
        and connector.config.public_demo
        and _is_bundled_database(connector.config.database_path)
    )


def _safe_int(value: str | None, default: int) -> int:
    try:
        return max(1, int(value or default))
    except ValueError:
        return default


def _require_read_query(sql: str) -> None:
    if not is_safe_sql(sql):
        raise ValueError("Only one read-only SELECT or WITH query is allowed.")


def _sqlite_read_authorizer(action: int, arg1: str | None, arg2: str | None, database: str | None, source: str | None) -> int:
    allowed = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION, sqlite3.SQLITE_RECURSIVE}
    if action == sqlite3.SQLITE_FUNCTION and (arg2 or "").lower() in {"load_extension", "writefile", "readfile"}:
        return sqlite3.SQLITE_DENY
    return sqlite3.SQLITE_OK if action in allowed else sqlite3.SQLITE_DENY


connector_registry = ConnectorRegistry()


__all__ = [
    "ConnectorConfig",
    "ConnectorHealth",
    "ConnectorRegistry",
    "ConnectorTelemetryEvent",
    "DataConnector",
    "PostgresConnector",
    "PostgresConnectorConfig",
    "SQLiteConnector",
    "SQLiteConnectorConfig",
    "connector_registry",
    "connector_environment_diagnostics",
    "get_connector_registry",
]
