from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from backend import auth_sessions
from backend.persistence import PersistenceError


def _button(app, label):
    return next(button for button in app.button if button.label == label)


def _run_button(app, label):
    _button(app, label).click().run()
    assert not app.exception, [item.message for item in app.exception]


def _login_form(passwords):
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py", default_timeout=30).run()
    assert not app.exception
    next(field for field in app.text_input if field.label == "Username").set_value("admin")
    next(field for field in app.text_input if field.label == "Password").set_value(passwords["admin"])
    return app


def test_login_storage_failure_is_recoverable_without_showing_connection_details(monkeypatch, isolated_auth_config):
    monkeypatch.setenv("OPENAI_API_KEY", "")
    app = _login_form(isolated_auth_config)
    original = auth_sessions.build_auth_session_repository

    def unavailable():
        raise RuntimeError("PRIVATE_STORE_DETAILS")

    monkeypatch.setattr(auth_sessions, "build_auth_session_repository", unavailable)
    _run_button(app, "Login")
    assert any("Sign-in is temporarily unavailable" in error.value for error in app.error)
    assert not any("PRIVATE_STORE_DETAILS" in error.value for error in app.error)
    assert "auth_session" not in app.session_state
    assert not any(button.label == "Try sample data" for button in app.button)
    monkeypatch.setattr(auth_sessions, "build_auth_session_repository", original)
    _run_button(app, "Login")
    assert app.session_state["auth_session"]["user_id"] == "admin"


@pytest.mark.parametrize("already_absent_on_retry", [False, True])
def test_failed_logout_clears_data_and_blocks_work_until_revocation_is_confirmed(
    monkeypatch, isolated_auth_config, already_absent_on_retry,
):
    monkeypatch.setenv("OPENAI_API_KEY", "")
    app = _login_form(isolated_auth_config)
    _run_button(app, "Login")
    _run_button(app, "Try sample data")
    token = app.session_state["auth_session"]["session_token"]
    repository = auth_sessions.build_auth_session_repository()
    delete_session = repository.delete_session

    def unavailable(*args, **kwargs):
        raise RuntimeError("PRIVATE_STORE_DETAILS")

    monkeypatch.setattr(repository, "delete_session", unavailable)
    monkeypatch.setattr(auth_sessions, "build_auth_session_repository", lambda: repository)
    _run_button(app, "Logout")
    assert "auth_session" not in app.session_state
    assert "uploaded_df" not in app.session_state
    assert app.session_state["latest_df"] is None
    assert app.session_state["pending_logout_token"]
    assert repository.get_session(token) is not None
    assert any("Server sign-out could not be confirmed" in warning.value for warning in app.warning)
    assert not any("PRIVATE_STORE_DETAILS" in warning.value for warning in app.warning)
    assert not any(token in warning.value for warning in app.warning)
    assert not any(button.label in {"Login", "Try sample data", "Get answer"} for button in app.button)
    assert not any(field.label == "Password" for field in app.text_input)

    _run_button(app, "Retry sign out")
    assert app.session_state["pending_logout_token"]
    monkeypatch.setattr(repository, "delete_session", delete_session)
    if already_absent_on_retry:
        delete_session(token)
    _run_button(app, "Retry sign out")
    assert "pending_logout_token" not in app.session_state
    assert repository.get_session(token) is None
    assert any("Sign-out confirmed" in item.value for item in app.success)
    assert any(button.label == "Login" for button in app.button)
    assert "uploaded_df" not in app.session_state


def test_checked_revocation_distinguishes_an_absent_token_from_storage_failure(monkeypatch, isolated_auth_config):
    assert auth_sessions.revoke_session_checked("nonexistent-test-session") is False

    def unavailable():
        raise RuntimeError("PRIVATE_STORE_DETAILS")

    monkeypatch.setattr(auth_sessions, "build_auth_session_repository", unavailable)
    with pytest.raises(PersistenceError, match="Sign-out could not be confirmed"):
        auth_sessions.revoke_session_checked("nonexistent-test-session")
