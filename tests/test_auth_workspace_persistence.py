from __future__ import annotations

import shutil
import json
import threading
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import backend.auth_sessions as auth_sessions
import workspace
from backend.auth_context import get_request_session
from backend.main import app
from backend.persistence import PersistenceError, build_auth_session_repository


def _runtime_dir() -> Path:
    path = Path.cwd() / ".auth_test_runtime" / uuid4().hex
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_auth_session_lifecycle_uses_file_backed_tokens(monkeypatch, isolated_auth_config) -> None:
    runtime_dir = _runtime_dir()
    monkeypatch.setattr(auth_sessions, "AUTH_SESSION_PATH", runtime_dir / "auth_sessions.json")

    try:
        identity = auth_sessions.login_user("admin", isolated_auth_config["admin"])

        assert identity is not None
        assert identity["authenticated"] is True
        assert auth_sessions.validate_session_token(identity["session_token"])["user_id"] == "admin"
        assert auth_sessions.revoke_session(identity["session_token"]) is True
        assert auth_sessions.validate_session_token(identity["session_token"]) is None
    finally:
        shutil.rmtree(runtime_dir.parent, ignore_errors=True)


def test_password_hashing_and_invalid_credentials(monkeypatch, isolated_auth_config) -> None:
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


def test_fastapi_auth_headers_resolve_request_session(monkeypatch, isolated_auth_config) -> None:
    runtime_dir = _runtime_dir()
    monkeypatch.setattr(auth_sessions, "AUTH_SESSION_PATH", runtime_dir / "auth_sessions.json")
    try:
        identity = auth_sessions.login_user("analyst", isolated_auth_config["analyst"])

        session = get_request_session(x_session_token=identity["session_token"])

        assert session.user_id == "analyst"
        assert session.workspace_id == "default-team.analyst"
        assert "workspace:analyst" in session.roles
    finally:
        shutil.rmtree(runtime_dir.parent, ignore_errors=True)


def test_auth_config_validation_reports_hash_support(monkeypatch, isolated_auth_config) -> None:
    runtime_dir = _runtime_dir()
    monkeypatch.setattr(auth_sessions, "AUTH_SESSION_PATH", runtime_dir / "auth_sessions.json")
    try:
        validation = auth_sessions.validate_auth_config()

        assert validation["supports_password_hashes"] is True
        assert validation["user_count"] >= 1
        assert validation["session_ttl_hours"] >= 1
    finally:
        shutil.rmtree(runtime_dir.parent, ignore_errors=True)


def test_auth_and_workspace_persistence_api(monkeypatch, isolated_auth_config) -> None:
    runtime_dir = _runtime_dir()
    monkeypatch.setattr(auth_sessions, "AUTH_SESSION_PATH", runtime_dir / "auth_sessions.json")
    monkeypatch.setattr(workspace, "WORKSPACE_DIR", runtime_dir / "workspaces")
    try:
        client = TestClient(app)

        login = client.post(
            "/auth/login", json={"username": "admin", "password": isolated_auth_config["admin"]}
        ).json()
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
            json={"title": "Executive summary", "scope": "analytics", "summary": "Healthy", "payload": {"rows": 1}, "visibility": "team"},
            headers=headers,
        ).json()
        team_workspace_id = workspace_id.split(".", 1)[0] + ".shared"
        shared_report = client.post(
            f"/workspace/{team_workspace_id}/reports",
            json={"title": "Shared dashboard", "scope": "dashboard", "summary": "Team view", "payload": {}, "visibility": "team"},
            headers=headers,
        ).json()
        fetched = client.get(f"/workspace/{workspace_id}", headers=headers).json()
        shared_fetched = client.get(f"/workspace/{team_workspace_id}", headers=headers).json()
        session_status = client.get("/auth/session", headers=headers).json()
        unauthorized = client.get(f"/workspace/{workspace_id}")
        logout = client.post("/auth/logout", json={"session_token": token}).json()

        assert saved_sql["items"][0]["sql"] == "select 1"
        assert saved_investigation["investigations"][0]["summary"] == "Found anomaly"
        assert saved_preferences["preferences"]["default_route"] == "Operations"
        saved_report_item = [item for item in saved_report["reports"] if item.get("title") == "Executive summary"][-1]
        shared_report_item = [item for item in shared_report["reports"] if item.get("title") == "Shared dashboard"][-1]
        assert saved_report_item["visibility"] == "team"
        assert shared_report_item["title"] == "Shared dashboard"
        assert fetched["query_history"][0]["saved"] is True
        assert fetched["saved_reports"][0]["summary"] == "Healthy"
        assert fetched["recent_activity"]
        assert shared_fetched["workspace_id"] == team_workspace_id
        assert any(item.get("visibility") == "team" for item in shared_fetched["saved_reports"])
        assert any(item.get("event_type") == "report_shared" for item in shared_fetched["collaboration_events"])
        assert session_status["authenticated"] is True
        assert unauthorized.status_code == 401
        assert logout["revoked"] is True
    finally:
        shutil.rmtree(runtime_dir.parent, ignore_errors=True)


def test_stale_session_validation_cannot_restore_a_revoked_token(monkeypatch, isolated_auth_config):
    identity = auth_sessions.login_user("admin", isolated_auth_config["admin"])
    token = identity["session_token"]
    repository = build_auth_session_repository()
    original_get = repository.get_session
    original_list = repository.list_sessions
    captured = threading.Event()
    resume = threading.Event()
    errors = []

    def pause_validation(snapshot):
        if threading.current_thread().name == "stale-session-validation":
            captured.set()
            if not resume.wait(5):
                raise RuntimeError("Controlled validation did not resume")
        return snapshot

    def validate():
        try:
            auth_sessions.validate_session_token(token)
        except Exception as exc:
            errors.append(exc)

    monkeypatch.setattr(repository, "get_session", lambda value: pause_validation(original_get(value)))
    # Also intercept the old bulk path so the regression catches its stale-snapshot write.
    monkeypatch.setattr(repository, "list_sessions", lambda: pause_validation(original_list()))
    monkeypatch.setattr(auth_sessions, "build_auth_session_repository", lambda: repository)
    checker = threading.Thread(target=validate, name="stale-session-validation")
    checker.start()
    try:
        assert captured.wait(5), "Validation did not read its snapshot"
        assert auth_sessions.revoke_session(token) is True
        assert original_get(token) is None
    finally:
        resume.set()
        checker.join(5)
    assert not checker.is_alive()
    assert not errors
    assert original_get(token) is None
    assert auth_sessions.validate_session_token(token) is None


@pytest.mark.parametrize("environment", ["test", "production"])
def test_auth_storage_failure_never_falls_back_to_stale_json(monkeypatch, isolated_auth_config, environment):
    identity = auth_sessions.login_user("admin", isolated_auth_config["admin"])
    token = identity["session_token"]
    payload = build_auth_session_repository().get_session(token)
    stale_contents = json.dumps({token: payload})
    auth_sessions.AUTH_SESSION_PATH.write_text(stale_contents)
    assert auth_sessions.revoke_session(token) is True
    monkeypatch.setenv("APP_ENV", environment)

    def unavailable_repository():
        raise PersistenceError("Storage unavailable")

    monkeypatch.setattr(auth_sessions, "build_auth_session_repository", unavailable_repository)
    assert auth_sessions.validate_session_token(token) is None
    assert auth_sessions.revoke_session(token) is False
    with pytest.raises(PersistenceError, match="could not be persisted"):
        auth_sessions.login_user("admin", isolated_auth_config["admin"])
    assert auth_sessions.AUTH_SESSION_PATH.read_text() == stale_contents


@pytest.mark.parametrize("expires_at", ["2000-01-01T00:00:00+00:00", "2099-01-01T00:00:00", "not-a-date"])
def test_expired_or_malformed_expiry_cannot_authenticate(isolated_auth_config, expires_at):
    token = "invalid-expiry-session"
    build_auth_session_repository().create_session(token, {
        "session_token": token,
        "user_id": "admin",
        "display_name": "Test Admin",
        "team_id": "default-team",
        "workspace_id": "default-team.admin",
        "role": "admin",
        "created_at": "2000-01-01T00:00:00+00:00",
        "expires_at": expires_at,
    })
    assert auth_sessions.validate_session_token(token) is None
