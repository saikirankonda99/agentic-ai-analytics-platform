from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def isolated_auth_config(monkeypatch, tmp_path):
    """Use explicit test users and storage, independently of developer or CI credentials."""
    import backend.auth_sessions as auth_sessions
    import workspace

    passwords = {role: f"test-{role}-password" for role in ("admin", "analyst", "viewer")}
    users = {
        role: {
            "password_hash": auth_sessions.hash_password(password),
            "display_name": f"Test {role}",
            "team_id": "default-team",
            "role": role,
        }
        for role, password in passwords.items()
    }
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("AUTH_USERS", json.dumps(users))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'platform.db'}")
    monkeypatch.setattr(auth_sessions, "AUTH_SESSION_PATH", tmp_path / "auth-sessions.json")
    monkeypatch.setattr(workspace, "WORKSPACE_DIR", tmp_path / "workspaces")
    return passwords


@pytest.fixture
def authenticated_api_client(isolated_auth_config):
    """Opt-in authenticated client; anonymous security assertions use their own client."""
    from backend.main import app

    with TestClient(app) as client:
        response = client.post(
            "/auth/login", json={"username": "admin", "password": isolated_auth_config["admin"]}
        )
        assert response.status_code == 200, response.text
        client.headers["X-Session-Token"] = response.json()["session"]["session_token"]
        yield client
