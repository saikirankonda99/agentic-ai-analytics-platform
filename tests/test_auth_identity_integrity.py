from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from backend import auth_sessions
from backend.persistence import build_auth_session_repository


def _set_users(monkeypatch, users):
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("AUTH_USERS", json.dumps(users))


def _user(team="retail", *, role="analyst"):
    return {"password": "synthetic-password", "team_id": team, "role": role}


@pytest.mark.parametrize("users", [
    {"alice smith": _user()},
    {"alice@example.com": _user()},
    {"-alice": _user()},
    {"alice-": _user()},
    {"": _user()},
    {"alice": _user("Retail Shop")},
    {"alice": _user("../retail")},
    {"alice": _user(12)},
    {"shared": _user()},
    {"Shared": _user()},
    {"branch.shared": _user()},
    {"sam": _user("acme.north"), "north.sam": _user("acme")},
    {"north.shared": _user("acme"), "other": _user("acme.north")},
    {"alice+shop": _user(), "alice-shop": _user()},
])
def test_ambiguous_or_sanitized_auth_identifiers_fail_closed(monkeypatch, users):
    _set_users(monkeypatch, users)
    assert auth_sessions.configured_users() == {}
    assert not auth_sessions.validate_auth_config()["valid"]


def test_unambiguous_canonical_ids_are_preserved(monkeypatch, isolated_auth_config):
    _set_users(monkeypatch, {"alice.smith": _user("retail-west"), "bob": _user("retail.east")})
    assert set(auth_sessions.configured_users()) == {"alice.smith", "bob"}
    alice = auth_sessions.login_user("alice.smith", "synthetic-password")
    bob = auth_sessions.login_user("bob", "synthetic-password")
    assert alice["workspace_id"] == "retail-west.alice.smith"
    assert bob["workspace_id"] == "retail.east.bob"
    assert auth_sessions.validate_session_token(alice["session_token"])["team_id"] == "retail-west"


@pytest.mark.parametrize("change", ["role", "team", "display", "remove", "password"])
def test_config_changes_revoke_existing_sessions(monkeypatch, isolated_auth_config, change):
    original = json.loads(os.environ["AUTH_USERS"])
    session = auth_sessions.login_user("admin", isolated_auth_config["admin"])
    token = session["session_token"]
    changed = json.loads(json.dumps(original))
    if change == "role":
        changed["admin"]["role"] = "viewer"
    elif change == "team":
        changed["admin"]["team_id"] = "new-team"
    elif change == "display":
        changed["admin"]["display_name"] = "Updated operator"
    elif change == "password":
        changed["admin"]["password_hash"] = auth_sessions.hash_password("new-test-password")
    else:
        del changed["admin"]
    monkeypatch.setenv("AUTH_USERS", json.dumps(changed))
    assert auth_sessions.validate_session_token(token) is None
    assert build_auth_session_repository().get_session(token) is None
    # Restoring an earlier config must not resurrect the invalidated token.
    monkeypatch.setenv("AUTH_USERS", json.dumps(original))
    assert auth_sessions.validate_session_token(token) is None


def test_development_credentials_survive_cache_restart_and_password_change_revokes(monkeypatch, isolated_auth_config):
    monkeypatch.delenv("AUTH_USERS", raising=False)
    monkeypatch.setenv("AUTH_ADMIN_PASSWORD", "initial-test-password")
    session = auth_sessions.login_user("admin", "initial-test-password")
    token = session["session_token"]
    verified_user = auth_sessions.authenticate_user("admin", "initial-test-password")
    auth_sessions._configured_user_snapshot.cache_clear()
    assert auth_sessions.create_session(verified_user).user_id == "admin"
    assert auth_sessions.validate_session_token(token)["role"] == "admin"
    monkeypatch.setenv("AUTH_ADMIN_PASSWORD", "replacement-test-password")
    assert auth_sessions.validate_session_token(token) is None


def test_validation_does_not_rehash_passwords_or_expose_fingerprints(monkeypatch, isolated_auth_config):
    _set_users(monkeypatch, {"operator": _user()})
    session = auth_sessions.login_user("operator", "synthetic-password")
    token = session["session_token"]
    stored = build_auth_session_repository().get_session(token)
    assert len(stored["auth_fingerprint"]) == 64
    assert "auth_fingerprint" not in session
    assert "credential_fingerprint" not in session
    assert "password_hash" not in session
    assert "synthetic-password" not in json.dumps(stored)

    def unexpected_hash(*args, **kwargs):
        pytest.fail("Unchanged session validation rehashed configured passwords")

    monkeypatch.setattr(auth_sessions, "hash_password", unexpected_hash)
    for _ in range(3):
        assert auth_sessions.validate_session_token(token)["user_id"] == "operator"


@pytest.mark.parametrize("field,value", [
    ("role", "viewer"), ("team_id", "other-team"), ("workspace_id", "other-team.admin"),
    ("display_name", "Different identity"), ("auth_fingerprint", ""),
])
def test_mismatched_or_legacy_session_identity_is_rejected(isolated_auth_config, field, value):
    session = auth_sessions.login_user("admin", isolated_auth_config["admin"])
    token = session["session_token"]
    repository = build_auth_session_repository()
    payload = repository.get_session(token)
    payload[field] = value
    repository.delete_session(token)
    repository.create_session(token, payload)
    assert auth_sessions.validate_session_token(token) is None
    assert repository.get_session(token) is None


def test_frontend_drops_admin_interface_when_configuration_changes(monkeypatch, isolated_auth_config):
    monkeypatch.setenv("OPENAI_API_KEY", "")
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py", default_timeout=30).run()
    next(field for field in app.text_input if field.label == "Username").set_value("admin")
    next(field for field in app.text_input if field.label == "Password").set_value(isolated_auth_config["admin"])
    next(button for button in app.button if button.label == "Login").click().run()
    app.radio(key="interface_mode").set_value("Admin workspace").run()
    assert not app.exception
    assert any(radio.key == "top_navigation" for radio in app.radio)

    users = json.loads(os.environ["AUTH_USERS"])
    users["admin"]["role"] = "viewer"
    monkeypatch.setenv("AUTH_USERS", json.dumps(users))
    app.run()
    assert not app.exception
    assert "auth_session" not in app.session_state
    assert not any(radio.key in {"interface_mode", "top_navigation"} for radio in app.radio)
    assert any(field.label == "Password" for field in app.text_input)
