from __future__ import annotations

import gc
import time
from pathlib import Path
from uuid import uuid4

from backend.persistence import (
    PersistenceSettings,
    SCHEMA_VERSION,
    WorkspaceDocument,
    build_auth_session_repository,
    build_workspace_repository,
    run_platform_migrations,
    validate_platform_database,
)
from workspace import build_user_session, load_workspace_memory, save_report_view, save_workspace_memory


def _sqlite_url(db_path: Path) -> str:
    return f"sqlite:///{db_path}"


def _runtime_db() -> Path:
    runtime_root = Path.cwd() / "data" / "test-runtime" / "platform-persistence"
    runtime_root.mkdir(parents=True, exist_ok=True)
    return runtime_root / f"platform-{uuid4().hex}.db"


def _cleanup_db(db_path: Path) -> None:
    gc.collect()
    for path in (db_path, db_path.with_suffix(".db-shm"), db_path.with_suffix(".db-wal")):
        for _ in range(3):
            try:
                path.unlink(missing_ok=True)
                break
            except PermissionError:
                time.sleep(0.05)


def test_sqlite_platform_migrations_and_workspace_repository(monkeypatch) -> None:
    db_path = _runtime_db()
    try:
        database_url = _sqlite_url(db_path)
        monkeypatch.setenv("DATABASE_URL", database_url)

        diagnostics = run_platform_migrations(database_url)
        repository = build_workspace_repository(database_url)
        saved = repository.save(
            WorkspaceDocument(
                workspace_id="team.user",
                team_id="team",
                memory={"workspace_id": "team.user", "team_id": "team", "saved_reports": [{"title": "Ops"}]},
            )
        )
        loaded = repository.get("team.user")

        assert diagnostics["backend"] == "sqlite"
        assert diagnostics["schema_version"] == SCHEMA_VERSION
        assert saved.updated_at
        assert loaded is not None
        assert loaded.memory["saved_reports"][0]["title"] == "Ops"
    finally:
        _cleanup_db(db_path)


def test_auth_session_repository_persists_sessions_and_users() -> None:
    db_path = _runtime_db()
    try:
        database_url = _sqlite_url(db_path)
        repository = build_auth_session_repository(database_url)
        payload = {
            "session_token": "sess-test",
            "user_id": "analyst",
            "workspace_id": "team.analyst",
            "created_at": "2026-05-19T00:00:00+00:00",
            "expires_at": "2026-05-20T00:00:00+00:00",
        }

        repository.save_user("analyst", {"role": "analyst"})
        repository.save_sessions({"sess-test": payload})

        assert repository.list_sessions()["sess-test"]["workspace_id"] == "team.analyst"
    finally:
        _cleanup_db(db_path)


def test_workspace_api_functions_use_durable_sqlite_repository(monkeypatch) -> None:
    db_path = _runtime_db()
    try:
        monkeypatch.setenv("DATABASE_URL", _sqlite_url(db_path))
        identity = build_user_session("durable.user", "team", "admin")
        memory = load_workspace_memory(identity)

        save_report_view(memory, {"title": "Durable report", "summary": "Still here"})
        save_workspace_memory(identity, memory)
        restored = load_workspace_memory(identity)

        assert restored["saved_reports"][0]["title"] == "Durable report"
        assert restored["workspace_id"] == identity["workspace_id"]
    finally:
        _cleanup_db(db_path)


def test_database_validation_reports_unavailable_postgres() -> None:
    diagnostics = validate_platform_database("postgresql://invalid:invalid@127.0.0.1:1/missing")

    assert diagnostics["backend"] == "postgresql"
    assert diagnostics["status"] == "error"
    assert diagnostics["error_type"]


def test_postgres_repository_selection(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/app")

    assert PersistenceSettings(database_url="postgresql://user:pass@localhost:5432/app").backend == "postgresql"
