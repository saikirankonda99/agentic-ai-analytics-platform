from __future__ import annotations

import json
import os
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Protocol

from backend.config import database_backend_for_url
from backend.redaction import redact_text


SCHEMA_VERSION = 2
DEFAULT_DATABASE_URL = "sqlite:///data/platform_persistence.db"


class PersistenceError(RuntimeError):
    """Raised when durable platform persistence is unavailable."""


@dataclass(frozen=True)
class PersistenceSettings:
    database_url: str = DEFAULT_DATABASE_URL
    retries: int = 2
    retry_delay_seconds: float = 0.05

    def __post_init__(self) -> None:
        database_backend_for_url(self.database_url)

    @property
    def backend(self) -> str:
        return database_backend_for_url(self.database_url)

    @property
    def sqlite_path(self) -> Path:
        prefix = "sqlite:///"
        if self.database_url.startswith(prefix):
            return Path(self.database_url.removeprefix(prefix))
        raise ValueError("A SQLite URL is required for a SQLite path.")


@dataclass(frozen=True)
class WorkspaceDocument:
    workspace_id: str
    team_id: str
    memory: dict[str, Any]
    updated_at: str | None = None


@dataclass(frozen=True)
class AuthSessionDocument:
    session_token: str
    user_id: str
    workspace_id: str
    payload: dict[str, Any]
    expires_at: str
    created_at: str


class WorkspaceRepository(Protocol):
    def get(self, workspace_id: str) -> WorkspaceDocument | None:
        """Load a workspace memory document."""

    def save(self, document: WorkspaceDocument) -> WorkspaceDocument:
        """Persist a workspace memory document."""

    def generation(self, workspace_id: str) -> int:
        """Return the deletion generation used to reject stale browser saves."""

    def delete(self, workspace_id: str, team_id: str) -> int:
        """Delete a workspace document and invalidate previously loaded copies."""

    def replace_if_unchanged(self, document: WorkspaceDocument, expected_json: Any) -> bool:
        """Prune an unchanged snapshot without overwriting another session's work."""


class AuthSessionRepository(Protocol):
    def save_user(self, username: str, payload: dict[str, Any]) -> None:
        """Persist user metadata discovered from runtime auth configuration."""

    def get_session(self, session_token: str) -> dict[str, Any] | None:
        """Read one current session without modifying any tokens."""

    def create_session(self, session_token: str, payload: dict[str, Any]) -> None:
        """Insert a new session without replacing any existing session."""

    def delete_session(self, session_token: str) -> bool:
        """Atomically delete one session and report whether it existed."""

    def list_sessions(self) -> dict[str, dict[str, Any]]:
        """Load auth session payloads keyed by token."""

    def save_sessions(self, sessions: dict[str, dict[str, Any]]) -> None:
        """Replace active auth session set transactionally."""


def persistence_settings() -> PersistenceSettings:
    return PersistenceSettings(
        database_url=os.getenv("DATABASE_URL")
        or os.getenv("PLATFORM_DATABASE_URL")
        or DEFAULT_DATABASE_URL,
        retries=max(0, int(os.getenv("DATABASE_RETRIES", "2"))),
        retry_delay_seconds=max(0.0, float(os.getenv("DATABASE_RETRY_DELAY_SECONDS", "0.05"))),
    )


class SQLitePlatformStore:
    def __init__(self, database_url: str | None = None) -> None:
        self.settings = PersistenceSettings(database_url=database_url or persistence_settings().database_url)
        self.db_path = self.settings.sqlite_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.db_path, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS platform_users (
                    username TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS auth_sessions (
                    session_token TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    workspace_id TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_auth_sessions_workspace
                    ON auth_sessions(workspace_id, expires_at);

                CREATE TABLE IF NOT EXISTS workspace_documents (
                    workspace_id TEXT PRIMARY KEY,
                    team_id TEXT NOT NULL,
                    memory_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_workspace_documents_team
                    ON workspace_documents(team_id, updated_at);

                CREATE TABLE IF NOT EXISTS workspace_generations (
                    workspace_id TEXT PRIMARY KEY,
                    generation INTEGER NOT NULL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS persistence_errors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    operation TEXT NOT NULL,
                    backend TEXT NOT NULL,
                    message TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            connection.execute(
                "INSERT OR IGNORE INTO schema_migrations (version) VALUES (?)",
                (SCHEMA_VERSION,),
            )

    def diagnostics(self) -> dict[str, Any]:
        started = time.perf_counter()
        with self.connect() as connection:
            version = connection.execute("SELECT MAX(version) AS version FROM schema_migrations").fetchone()["version"]
        return {
            "backend": "sqlite",
            "database": str(self.db_path),
            "schema_version": version,
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
            "status": "ok",
        }


class SQLiteWorkspaceRepository(SQLitePlatformStore):
    def replace_if_unchanged(self, document: WorkspaceDocument, expected_json: Any) -> bool:
        expected = expected_json if isinstance(expected_json, str) else json.dumps(expected_json, sort_keys=True)
        with self.connect() as connection:
            changed = connection.execute(
                "UPDATE workspace_documents SET memory_json = ?, updated_at = CURRENT_TIMESTAMP "
                "WHERE workspace_id = ? AND team_id = ? AND memory_json = ?",
                (json.dumps(document.memory, sort_keys=True), document.workspace_id, document.team_id, expected),
            ).rowcount
        return changed == 1

    def generation(self, workspace_id: str) -> int:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT generation FROM workspace_generations WHERE workspace_id = ?", (workspace_id,)
            ).fetchone()
        return int(row["generation"]) if row else 0

    def delete(self, workspace_id: str, team_id: str) -> int:
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT team_id FROM workspace_documents WHERE workspace_id = ?", (workspace_id,)
            ).fetchone()
            if row and row["team_id"] != team_id:
                raise PersistenceError("Workspace ownership does not match.")
            connection.execute(
                "INSERT INTO workspace_generations (workspace_id, generation) VALUES (?, 1) "
                "ON CONFLICT(workspace_id) DO UPDATE SET generation = generation + 1", (workspace_id,)
            )
            return connection.execute(
                "DELETE FROM workspace_documents WHERE workspace_id = ? AND team_id = ?", (workspace_id, team_id)
            ).rowcount

    def get(self, workspace_id: str) -> WorkspaceDocument | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT workspace_id, team_id, memory_json, updated_at FROM workspace_documents WHERE workspace_id = ?",
                (workspace_id,),
            ).fetchone()
        if row is None:
            return None
        return WorkspaceDocument(
            workspace_id=row["workspace_id"],
            team_id=row["team_id"],
            memory=json.loads(row["memory_json"] or "{}"),
            updated_at=row["updated_at"],
        )

    def save(self, document: WorkspaceDocument) -> WorkspaceDocument:
        payload = json.dumps(document.memory, sort_keys=True)
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            owner = connection.execute(
                "SELECT team_id FROM workspace_documents WHERE workspace_id = ?", (document.workspace_id,)
            ).fetchone()
            if owner and owner["team_id"] != document.team_id:
                raise PersistenceError("Workspace ownership does not match.")
            row = connection.execute(
                "SELECT generation FROM workspace_generations WHERE workspace_id = ?", (document.workspace_id,)
            ).fetchone()
            if document.memory.get("_data_generation", 0) != (int(row["generation"]) if row else 0):
                raise PersistenceError("Workspace data was deleted in another session. Reload before saving.")
            connection.execute(
                """
                INSERT INTO workspace_documents (workspace_id, team_id, memory_json)
                VALUES (?, ?, ?)
                ON CONFLICT(workspace_id) DO UPDATE SET
                    team_id = excluded.team_id,
                    memory_json = excluded.memory_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (document.workspace_id, document.team_id, payload),
            )
            row = connection.execute(
                "SELECT updated_at FROM workspace_documents WHERE workspace_id = ?",
                (document.workspace_id,),
            ).fetchone()
        return WorkspaceDocument(
            workspace_id=document.workspace_id,
            team_id=document.team_id,
            memory=document.memory,
            updated_at=row["updated_at"] if row else document.updated_at,
        )


class SQLiteAuthSessionRepository(SQLitePlatformStore):
    def save_user(self, username: str, payload: dict[str, Any]) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO platform_users (username, payload_json)
                VALUES (?, ?)
                ON CONFLICT(username) DO UPDATE SET
                    payload_json = excluded.payload_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (username, json.dumps(payload, sort_keys=True)),
            )

    def get_session(self, session_token: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT payload_json FROM auth_sessions WHERE session_token = ?", (session_token,)
            ).fetchone()
        return json.loads(row["payload_json"]) if row is not None else None

    def create_session(self, session_token: str, payload: dict[str, Any]) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO auth_sessions (
                    session_token, user_id, workspace_id, payload_json, expires_at, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    session_token,
                    payload.get("user_id", ""),
                    payload.get("workspace_id", ""),
                    json.dumps(payload, sort_keys=True),
                    payload.get("expires_at", ""),
                    payload.get("created_at", ""),
                ),
            )

    def delete_session(self, session_token: str) -> bool:
        with self.connect() as connection:
            cursor = connection.execute("DELETE FROM auth_sessions WHERE session_token = ?", (session_token,))
            return cursor.rowcount > 0

    def list_sessions(self) -> dict[str, dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute("SELECT session_token, payload_json FROM auth_sessions").fetchall()
        return {row["session_token"]: json.loads(row["payload_json"] or "{}") for row in rows}

    def save_sessions(self, sessions: dict[str, dict[str, Any]]) -> None:
        with self.connect() as connection:
            connection.execute("DELETE FROM auth_sessions")
            connection.executemany(
                """
                INSERT INTO auth_sessions (
                    session_token, user_id, workspace_id, payload_json, expires_at, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        token,
                        payload.get("user_id", ""),
                        payload.get("workspace_id", ""),
                        json.dumps(payload, sort_keys=True),
                        payload.get("expires_at", ""),
                        payload.get("created_at", ""),
                    )
                    for token, payload in sessions.items()
                ],
            )


class PostgreSQLPlatformStore:
    def __init__(self, database_url: str | None = None) -> None:
        self.settings = PersistenceSettings(database_url=database_url or persistence_settings().database_url)
        self.initialize()

    @contextmanager
    def connect(self) -> Iterator[Any]:
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:  # pragma: no cover - dependency installed in production image
            raise PersistenceError("psycopg is required for PostgreSQL persistence") from exc
        connection = psycopg.connect(self.settings.database_url, row_factory=dict_row, connect_timeout=10)
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.execute("SELECT pg_advisory_xact_lock(%s)", (846231905,))
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS platform_users (
                    username TEXT PRIMARY KEY,
                    payload_json JSONB NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS auth_sessions (
                    session_token TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    workspace_id TEXT NOT NULL,
                    payload_json JSONB NOT NULL,
                    expires_at TIMESTAMPTZ NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_auth_sessions_workspace ON auth_sessions(workspace_id, expires_at)"
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS workspace_documents (
                    workspace_id TEXT PRIMARY KEY,
                    team_id TEXT NOT NULL,
                    memory_json JSONB NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_workspace_documents_team ON workspace_documents(team_id, updated_at)"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS workspace_generations "
                "(workspace_id TEXT PRIMARY KEY, generation INTEGER NOT NULL DEFAULT 0)"
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS persistence_errors (
                    id BIGSERIAL PRIMARY KEY,
                    operation TEXT NOT NULL,
                    backend TEXT NOT NULL,
                    message TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            connection.execute(
                "INSERT INTO schema_migrations (version) VALUES (%s) ON CONFLICT (version) DO NOTHING",
                (SCHEMA_VERSION,),
            )

    def diagnostics(self) -> dict[str, Any]:
        started = time.perf_counter()
        with self.connect() as connection:
            row = connection.execute("SELECT MAX(version) AS version FROM schema_migrations").fetchone()
        return {
            "backend": "postgresql",
            "schema_version": row["version"],
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
            "status": "ok",
        }


class PostgreSQLWorkspaceRepository(PostgreSQLPlatformStore):
    def replace_if_unchanged(self, document: WorkspaceDocument, expected_json: Any) -> bool:
        expected = expected_json if isinstance(expected_json, str) else json.dumps(expected_json, sort_keys=True)
        with self.connect() as connection:
            changed = connection.execute(
                "UPDATE workspace_documents SET memory_json = %s::jsonb, updated_at = NOW() "
                "WHERE workspace_id = %s AND team_id = %s AND memory_json = %s::jsonb",
                (json.dumps(document.memory, sort_keys=True), document.workspace_id, document.team_id, expected),
            ).rowcount
        return changed == 1

    def generation(self, workspace_id: str) -> int:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT generation FROM workspace_generations WHERE workspace_id = %s", (workspace_id,)
            ).fetchone()
        return int(row["generation"]) if row else 0

    def delete(self, workspace_id: str, team_id: str) -> int:
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO workspace_generations (workspace_id) VALUES (%s) ON CONFLICT DO NOTHING", (workspace_id,)
            )
            connection.execute(
                "SELECT generation FROM workspace_generations WHERE workspace_id = %s FOR UPDATE", (workspace_id,)
            )
            row = connection.execute(
                "SELECT team_id FROM workspace_documents WHERE workspace_id = %s", (workspace_id,)
            ).fetchone()
            if row and row["team_id"] != team_id:
                raise PersistenceError("Workspace ownership does not match.")
            connection.execute(
                "UPDATE workspace_generations SET generation = generation + 1 WHERE workspace_id = %s", (workspace_id,)
            )
            return connection.execute(
                "DELETE FROM workspace_documents WHERE workspace_id = %s AND team_id = %s", (workspace_id, team_id)
            ).rowcount

    def get(self, workspace_id: str) -> WorkspaceDocument | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT workspace_id, team_id, memory_json, updated_at FROM workspace_documents WHERE workspace_id = %s",
                (workspace_id,),
            ).fetchone()
        if row is None:
            return None
        return WorkspaceDocument(
            workspace_id=row["workspace_id"],
            team_id=row["team_id"],
            memory=dict(row["memory_json"] or {}),
            updated_at=str(row["updated_at"]) if row.get("updated_at") else None,
        )

    def save(self, document: WorkspaceDocument) -> WorkspaceDocument:
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO workspace_generations (workspace_id) VALUES (%s) ON CONFLICT DO NOTHING", (document.workspace_id,)
            )
            generation = connection.execute(
                "SELECT generation FROM workspace_generations WHERE workspace_id = %s FOR UPDATE", (document.workspace_id,)
            ).fetchone()["generation"]
            owner = connection.execute(
                "SELECT team_id FROM workspace_documents WHERE workspace_id = %s", (document.workspace_id,)
            ).fetchone()
            if owner and owner["team_id"] != document.team_id:
                raise PersistenceError("Workspace ownership does not match.")
            if document.memory.get("_data_generation", 0) != generation:
                raise PersistenceError("Workspace data was deleted in another session. Reload before saving.")
            row = connection.execute(
                """
                INSERT INTO workspace_documents (workspace_id, team_id, memory_json)
                VALUES (%s, %s, %s::jsonb)
                ON CONFLICT (workspace_id) DO UPDATE SET
                    team_id = EXCLUDED.team_id,
                    memory_json = EXCLUDED.memory_json,
                    updated_at = NOW()
                RETURNING updated_at
                """,
                (document.workspace_id, document.team_id, json.dumps(document.memory, sort_keys=True)),
            ).fetchone()
        return WorkspaceDocument(
            workspace_id=document.workspace_id,
            team_id=document.team_id,
            memory=document.memory,
            updated_at=str(row["updated_at"]) if row else document.updated_at,
        )


class PostgreSQLAuthSessionRepository(PostgreSQLPlatformStore):
    def save_user(self, username: str, payload: dict[str, Any]) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO platform_users (username, payload_json)
                VALUES (%s, %s::jsonb)
                ON CONFLICT (username) DO UPDATE SET
                    payload_json = EXCLUDED.payload_json,
                    updated_at = NOW()
                """,
                (username, json.dumps(payload, sort_keys=True)),
            )

    def get_session(self, session_token: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT payload_json FROM auth_sessions WHERE session_token = %s", (session_token,)
            ).fetchone()
        return dict(row["payload_json"]) if row is not None else None

    def create_session(self, session_token: str, payload: dict[str, Any]) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO auth_sessions (
                    session_token, user_id, workspace_id, payload_json, expires_at, created_at
                )
                VALUES (%s, %s, %s, %s::jsonb, %s, %s)
                """,
                (
                    session_token,
                    payload.get("user_id", ""),
                    payload.get("workspace_id", ""),
                    json.dumps(payload, sort_keys=True),
                    payload.get("expires_at", ""),
                    payload.get("created_at", ""),
                ),
            )

    def delete_session(self, session_token: str) -> bool:
        with self.connect() as connection:
            cursor = connection.execute("DELETE FROM auth_sessions WHERE session_token = %s", (session_token,))
            return cursor.rowcount > 0

    def list_sessions(self) -> dict[str, dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute("SELECT session_token, payload_json FROM auth_sessions").fetchall()
        return {row["session_token"]: dict(row["payload_json"] or {}) for row in rows}

    def save_sessions(self, sessions: dict[str, dict[str, Any]]) -> None:
        with self.connect() as connection:
            connection.execute("DELETE FROM auth_sessions")
            for token, payload in sessions.items():
                connection.execute(
                    """
                    INSERT INTO auth_sessions (
                        session_token, user_id, workspace_id, payload_json, expires_at, created_at
                    )
                    VALUES (%s, %s, %s, %s::jsonb, %s, %s)
                    """,
                    (
                        token,
                        payload.get("user_id", ""),
                        payload.get("workspace_id", ""),
                        json.dumps(payload, sort_keys=True),
                        payload.get("expires_at", ""),
                        payload.get("created_at", ""),
                    ),
                )


def build_workspace_repository(database_url: str | None = None) -> WorkspaceRepository:
    settings = PersistenceSettings(database_url=database_url or persistence_settings().database_url)
    if settings.backend == "postgresql":
        return PostgreSQLWorkspaceRepository(settings.database_url)
    return SQLiteWorkspaceRepository(settings.database_url)


def build_auth_session_repository(database_url: str | None = None) -> AuthSessionRepository:
    settings = PersistenceSettings(database_url=database_url or persistence_settings().database_url)
    if settings.backend == "postgresql":
        return PostgreSQLAuthSessionRepository(settings.database_url)
    return SQLiteAuthSessionRepository(settings.database_url)


def run_platform_migrations(database_url: str | None = None) -> dict[str, Any]:
    settings = PersistenceSettings(database_url=database_url or persistence_settings().database_url)
    store = PostgreSQLPlatformStore(settings.database_url) if settings.backend == "postgresql" else SQLitePlatformStore(settings.database_url)
    return store.diagnostics()


def validate_platform_database(database_url: str | None = None) -> dict[str, Any]:
    try:
        return run_platform_migrations(database_url)
    except Exception as exc:
        settings = PersistenceSettings(database_url=database_url or persistence_settings().database_url)
        return {
            "backend": settings.backend,
            "status": "error",
            "schema_version": None,
            "error_type": type(exc).__name__,
            "message": redact_text(str(exc)),
        }


__all__ = [
    "AuthSessionDocument",
    "AuthSessionRepository",
    "PersistenceError",
    "PersistenceSettings",
    "SCHEMA_VERSION",
    "SQLiteAuthSessionRepository",
    "SQLitePlatformStore",
    "SQLiteWorkspaceRepository",
    "WorkspaceDocument",
    "WorkspaceRepository",
    "build_auth_session_repository",
    "build_workspace_repository",
    "persistence_settings",
    "run_platform_migrations",
    "validate_platform_database",
]
