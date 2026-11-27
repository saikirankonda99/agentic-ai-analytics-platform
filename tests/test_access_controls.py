from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from backend.main import app


def _login(client, username, password):
    response = client.post("/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return {"X-Session-Token": response.json()["session"]["session_token"]}


@pytest.mark.parametrize("headers", [
    {},
    {"X-User-Id": "admin", "X-Workspace-Id": "default-team.admin", "X-Organization-Id": "organization:default-team"},
    {"Authorization": "Bearer invalid", "X-User-Id": "admin", "X-Workspace-Id": "default-team.admin"},
])
def test_identity_headers_cannot_authenticate(headers, isolated_auth_config):
    client = TestClient(app)
    for path in ("/workspace/default-team.admin", "/workspace/default-team.admin/sql-history",
                 "/workspace/default-team.admin/transcripts", "/workspace/default-team.admin/inspection",
                 "/workflow/nonexistent", "/workflow/nonexistent/events", "/workflow/nonexistent/stream",
                 "/diagnostics", "/connectors/sqlite/schema", "/investigations/latest"):
        assert client.get(path, headers=headers).status_code == 401, path
    assert client.post("/execute", json={"question": "Synthetic request"}, headers=headers).status_code == 401
    assert client.post("/workspace/default-team.admin/reports", json={"title": "Synthetic"}, headers=headers).status_code == 401


def test_session_identity_ignores_spoofed_headers(authenticated_api_client):
    client = authenticated_api_client
    response = client.get("/auth/session", headers={
        "X-User-Id": "victim", "X-Workspace-Id": "other-team.victim", "X-Organization-Id": "organization:other-team",
    })
    identity = response.json()["request_session"]
    assert identity["user_id"] == "admin"
    assert identity["workspace_id"] == "default-team.admin"
    assert identity["organization_id"] == "organization:default-team"
    assert client.get("/workspace/other-team.victim").status_code == 403


def test_workflow_read_routes_and_websockets_enforce_ownership(authenticated_api_client, isolated_auth_config, monkeypatch):
    client = authenticated_api_client
    created = client.post("/execute", json={"question": "Synthetic orchestration check"}).json()
    workflow_id = created["workflow_id"]
    viewer_headers = _login(client, "viewer", isolated_auth_config["viewer"])
    for suffix in ("", "/events", "/telemetry", "/replay", "/execution-graph", "/telemetry/events", "/telemetry/aggregate", "/stream"):
        path = f"/workflow/{workflow_id}{suffix}"
        assert client.get(path).status_code == 200, path
        assert client.get(path, headers=viewer_headers).status_code == 403, path
    for path in ("/incidents", "/executive/report", "/audit/timeline"):
        assert client.get(path, params={"workflow_id": workflow_id}, headers=viewer_headers).status_code == 403

    anonymous = TestClient(app)
    with pytest.raises(WebSocketDisconnect):
        with anonymous.websocket_connect(f"/workflow/{workflow_id}/ws", headers={
            "X-User-Id": "admin", "X-Workspace-Id": "default-team.admin", "X-Organization-Id": "organization:default-team",
        }):
            pass
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f"/workflow/{workflow_id}/ws", headers=viewer_headers):
            pass
    with client.websocket_connect(f"/workflow/{workflow_id}/ws") as socket:
        assert "update_type" in socket.receive_json()


def test_viewer_can_read_shared_but_cannot_write_or_inspect_connectors(authenticated_api_client, isolated_auth_config):
    client = authenticated_api_client
    headers = _login(client, "viewer", isolated_auth_config["viewer"])
    assert client.get("/workspace/default-team.shared", headers=headers).status_code == 200
    assert client.get("/workspace/default-team.admin/transcripts", headers=headers).status_code == 403
    for workspace_id in ("default-team.viewer", "default-team.shared"):
        for suffix, payload in (
            ("sql-history", {"sql": "SELECT 1"}),
            ("reports", {"title": "Synthetic", "visibility": "team"}),
            ("investigations", {"investigation": {"summary": "Synthetic"}}),
            ("preferences", {"preferences": {"compact_results": True}}),
        ):
            assert client.post(f"/workspace/{workspace_id}/{suffix}", json=payload, headers=headers).status_code == 403
    assert client.get("/connectors/sqlite/schema", headers=headers).status_code == 403
    assert client.get("/diagnostics", headers=headers).status_code == 403


def test_analyst_save_preserves_role(authenticated_api_client, isolated_auth_config):
    client = authenticated_api_client
    headers = _login(client, "analyst", isolated_auth_config["analyst"])
    assert client.post("/workspace/default-team.shared/reports", json={"title": "Synthetic", "visibility": "team"}, headers=headers).status_code == 200
    memory = client.get("/workspace/default-team.shared", headers=headers).json()
    assert memory["members"]["analyst"]["role"] == "analyst"
    assert client.post("/workspace/default-team.shared/preferences", json={"preferences": {}}, headers=headers).status_code == 403


def test_unscoped_caches_are_unavailable(authenticated_api_client, monkeypatch):
    from backend.services import backend_service
    from api import app as legacy_app

    client = authenticated_api_client
    monkeypatch.setattr(backend_service.cache, "get", lambda *args: {"private": "must not be returned"})
    assert client.get("/investigations/latest").status_code == 503
    assert client.get("/workflow/workflow:latest").status_code == 400
    legacy = TestClient(legacy_app)
    assert legacy.get("/workflow/status").status_code == 401
    legacy.headers.update(dict(client.headers))
    assert legacy.get("/workflow/status").status_code == 503
    assert legacy.get("/telemetry").status_code == 503


def test_legacy_model_routes_require_authentication(isolated_auth_config, monkeypatch):
    from api import app as legacy_app
    from backend.services import backend_service

    def unexpected_call(*args, **kwargs):
        pytest.fail("Unauthenticated request reached the analytics service")

    monkeypatch.setattr(backend_service, "execute_query", unexpected_call)
    monkeypatch.setattr(backend_service, "run_investigation", unexpected_call)
    monkeypatch.setattr(backend_service, "executive_briefing", unexpected_call)
    client = TestClient(legacy_app)
    for path, payload in (("/query", {"question": "Synthetic"}), ("/investigations", {"question": "Synthetic", "sql": "SELECT 1"}), ("/briefings", {})):
        assert client.post(path, json=payload).status_code == 401


def test_logout_and_expiry_clear_uploaded_data(monkeypatch):
    import auth

    state = {"auth_session": {"session_token": "synthetic"}, "latest_df": [1], "uploaded_df": [2], "messages": ["private"]}
    ui = SimpleNamespace(session_state=state, rerun=lambda: None, warning=lambda *args: None, stop=lambda: None)
    monkeypatch.setattr(auth, "st", ui)
    monkeypatch.setattr(auth, "revoke_session", lambda token: True)
    auth.logout()
    assert state == {}
    state.update({"auth_session": {"session_token": "expired"}, "uploaded_df": [3], "analytics_memory": {"private": True}})
    monkeypatch.setattr(auth, "validate_session_token", lambda token: None)
    monkeypatch.setattr(auth, "login", lambda: None)
    auth.require_login()
    assert state == {}


@pytest.mark.parametrize("configuration", [None, "not-json", "[]", "{}", '{"admin":{"password":"example","role":"admin"}}'])
def test_production_auth_config_fails_closed(configuration, monkeypatch):
    import backend.auth_sessions as auth_sessions
    from backend.startup import _auth_check

    monkeypatch.setenv("APP_ENV", "production")
    if configuration is None:
        monkeypatch.delenv("AUTH_USERS", raising=False)
    else:
        monkeypatch.setenv("AUTH_USERS", configuration)
    assert auth_sessions.configured_users() == {}
    assert auth_sessions.validate_auth_config()["errors"]
    assert _auth_check().status == "error"


def test_production_accepts_explicit_password_hashes(monkeypatch):
    from backend.auth_sessions import hash_password, validate_auth_config

    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("AUTH_USERS", json.dumps({"operator": {"password_hash": hash_password("synthetic-test-password"), "role": "admin", "team_id": "retail"}}))
    assert validate_auth_config()["valid"] is True
