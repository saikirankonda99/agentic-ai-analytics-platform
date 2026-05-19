from __future__ import annotations

import shutil
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

import backend.auth_sessions as auth_sessions
import workspace
from backend.auth_context import get_request_session
from backend.main import app


def _runtime_dir() -> Path:
    path = Path.cwd() / ".auth_test_runtime" / uuid4().hex
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_auth_session_lifecycle_uses_file_backed_tokens(monkeypatch) -> None:
    runtime_dir = _runtime_dir()
    monkeypatch.setattr(auth_sessions, "AUTH_SESSION_PATH", runtime_dir / "auth_sessions.json")

    try:
        identity = auth_sessions.login_user("admin", "admin123")

        assert identity is not None
        assert identity["authenticated"] is True
        assert auth_sessions.validate_session_token(identity["session_token"])["user_id"] == "admin"
        assert auth_sessions.revoke_session(identity["session_token"]) is True
        assert auth_sessions.validate_session_token(identity["session_token"]) is None
    finally:
        shutil.rmtree(runtime_dir.parent, ignore_errors=True)


def test_password_hashing_and_invalid_credentials(monkeypatch) -> None:
    runtime_dir = _runtime_dir()
    monkeypatch.setattr(auth_sessions, "AUTH_SESSION_PATH", runtime_dir / "auth_sessions.json")
    try:
        password_hash = auth_sessions.hash_password("correct-password")

        assert password_hash != "correct-password"
        assert auth_sessions.verify_password("correct-password", password_hash) is True
        assert auth_sessions.verify_password("wrong-password", password_hash) is False
        assert auth_sessions.login_user("admin", "wrong-password") is None
    finally:
        shutil.rmtree(runtime_dir.parent, ignore_errors=True)


def test_fastapi_auth_headers_resolve_request_session(monkeypatch) -> None:
    runtime_dir = _runtime_dir()
    monkeypatch.setattr(auth_sessions, "AUTH_SESSION_PATH", runtime_dir / "auth_sessions.json")
    try:
        identity = auth_sessions.login_user("analyst", "analyst123")

        session = get_request_session(x_session_token=identity["session_token"])

        assert session.user_id == "analyst"
        assert session.workspace_id == "default-team.analyst"
        assert "workspace:analyst" in session.roles
    finally:
        shutil.rmtree(runtime_dir.parent, ignore_errors=True)


def test_auth_config_validation_reports_hash_support(monkeypatch) -> None:
    runtime_dir = _runtime_dir()
    monkeypatch.setattr(auth_sessions, "AUTH_SESSION_PATH", runtime_dir / "auth_sessions.json")
    try:
        validation = auth_sessions.validate_auth_config()

        assert validation["supports_password_hashes"] is True
        assert validation["user_count"] >= 1
        assert validation["session_ttl_hours"] >= 1
    finally:
        shutil.rmtree(runtime_dir.parent, ignore_errors=True)


def test_auth_and_workspace_persistence_api(monkeypatch) -> None:
    runtime_dir = _runtime_dir()
    monkeypatch.setattr(auth_sessions, "AUTH_SESSION_PATH", runtime_dir / "auth_sessions.json")
    monkeypatch.setattr(workspace, "WORKSPACE_DIR", runtime_dir / "workspaces")
    try:
        client = TestClient(app)

        login = client.post("/auth/login", json={"username": "admin", "password": "admin123"}).json()
        token = login["session"]["session_token"]
        headers = {"X-Session-Token": token}
        workspace_id = login["session"]["workspace_id"]

        saved_sql = client.post(
            f"/workspace/{workspace_id}/sql-history",
            json={"question": "List customers", "sql": "select 1", "rows": 1},
            headers=headers,
        ).json()
        saved_investigation = client.post(
            f"/workspace/{workspace_id}/investigations",
            json={"investigation": {"status": "completed", "summary": "Found anomaly"}, "note": "Review"},
            headers=headers,
        ).json()
        saved_preferences = client.post(
            f"/workspace/{workspace_id}/preferences",
            json={"preferences": {"default_route": "Operations", "compact_results": True}},
            headers=headers,
        ).json()
        saved_report = client.post(
            f"/workspace/{workspace_id}/reports",
            json={"title": "Executive summary", "scope": "analytics", "summary": "Healthy", "payload": {"rows": 1}},
            headers=headers,
        ).json()
        fetched = client.get(f"/workspace/{workspace_id}", headers=headers).json()
        session_status = client.get("/auth/session", headers=headers).json()
        unauthorized = client.get(f"/workspace/{workspace_id}")
        logout = client.post("/auth/logout", json={"session_token": token}).json()

        assert saved_sql["items"][0]["sql"] == "select 1"
        assert saved_investigation["investigations"][0]["summary"] == "Found anomaly"
        assert saved_preferences["preferences"]["default_route"] == "Operations"
        assert saved_report["reports"][0]["title"] == "Executive summary"
        assert fetched["query_history"][0]["saved"] is True
        assert fetched["saved_reports"][0]["summary"] == "Healthy"
        assert fetched["recent_activity"]
        assert session_status["authenticated"] is True
        assert unauthorized.status_code == 401
        assert logout["revoked"] is True
    finally:
        shutil.rmtree(runtime_dir.parent, ignore_errors=True)
