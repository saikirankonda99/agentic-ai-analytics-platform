from __future__ import annotations

from io import BytesIO
import os
from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from csv_analytics import DEMO_PATH
from backend.persistence import PersistenceError


def _button(app, label):
    return next(button for button in app.button if button.label == label)


def _click(app, label):
    _button(app, label).click().run()
    assert not app.exception, [item.message for item in app.exception]


def _login(passwords, role="admin"):
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py", default_timeout=30).run()
    assert not app.exception, [item.message for item in app.exception]
    next(field for field in app.text_input if field.label == "Username").set_value(role)
    next(field for field in app.text_input if field.label == "Password").set_value(passwords[role])
    _click(app, "Login")
    return app


def test_customer_first_flow_has_no_operator_navigation_and_calculates_sample(isolated_auth_config, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "")
    app = _login(isolated_auth_config)
    assert app.session_state["interface_mode"] == "Customer dashboard"
    assert not any(radio.key == "top_navigation" for radio in app.radio)
    assert not any(button.label in {"Run", "Revenue by Product", "Run scheduled check"} for button in app.button)

    _click(app, "Try sample data")
    assert app.session_state["latest_df"].to_dict("records") == [{"revenue": 352.0, "sales_rows": 12, "units": 28.0}]
    assert _button(app, "Explain this result with AI").disabled
    assert any(expander.label == "Common questions" and not expander.proto.expanded for expander in app.expander)
    _click(app, "Revenue by Product")
    result = app.session_state["latest_df"]
    assert dict(zip(result["product"], result["revenue"])) == {"Coffee Beans": 180.0, "Tea": 100.0, "Mug": 72.0}
    assert app.session_state["workflow_telemetry"]["total_tokens"] == 0
    next(field for field in app.text_input if field.label == "Your business question").set_value("Predict profit next year")
    _click(app, "Get answer")
    assert app.session_state["latest_df"] is None
    assert app.session_state["customer_ai_explanation"] is None


@pytest.mark.parametrize("role", ["analyst", "viewer"])
def test_nonadmins_cannot_switch_to_admin_views(isolated_auth_config, monkeypatch, role):
    monkeypatch.setenv("OPENAI_API_KEY", "")
    app = _login(isolated_auth_config, role)
    app.session_state["interface_mode"] = "Admin workspace"
    app.session_state["top_navigation"] = "API"
    app.session_state["workspace_route"] = "API"
    app.run()
    assert not app.exception
    assert app.session_state["interface_mode"] == "Customer dashboard"
    assert not any(radio.key in {"interface_mode", "top_navigation"} for radio in app.radio)
    assert not any(button.label == "Run scheduled check" for button in app.button)
    assert _button(app, "Try sample data")


def test_upload_review_and_results_survive_admin_preview_switch(isolated_auth_config, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "")
    upload = BytesIO(DEMO_PATH.read_bytes())
    upload.name = "shop-sales.csv"
    monkeypatch.setattr(st, "file_uploader", lambda *args, **kwargs: upload)
    app = _login(isolated_auth_config)
    assert app.session_state["csv_import_pending"]
    assert app.session_state["latest_df"] is None

    app.radio(key="interface_mode").set_value("Admin workspace").run()
    assert not app.exception
    assert app.session_state["csv_import_pending"]
    app.radio(key="interface_mode").set_value("Customer dashboard").run()
    assert not app.exception
    _click(app, "Use this data")
    assert not app.session_state["csv_import_pending"]
    assert app.session_state["latest_df"].iloc[0]["revenue"] == 352.0
    _click(app, "Monthly Revenue")
    expected = app.session_state["latest_df"].copy()

    app.radio(key="interface_mode").set_value("Admin workspace").run()
    assert not app.exception
    app.radio(key="interface_mode").set_value("Customer dashboard").run()
    assert not app.exception
    assert app.session_state["uploaded_name"] == "shop-sales.csv"
    assert app.session_state["latest_df"].equals(expected)
    monkeypatch.setattr(st, "file_uploader", lambda *args, **kwargs: None)
    _click(app, "Logout")
    assert "uploaded_df" not in app.session_state
    assert app.session_state["latest_df"] is None


@pytest.mark.parametrize("action", ["Remove active file", "Clear session"])
def test_customer_can_remove_active_data_without_erasing_saved_history(isolated_auth_config, monkeypatch, action):
    import workspace

    monkeypatch.setenv("OPENAI_API_KEY", "")
    app = _login(isolated_auth_config, "analyst")
    _click(app, "Try sample data")
    _click(app, "Revenue by Product")
    identity = dict(app.session_state["user_identity"])
    before = workspace.load_workspace_memory(identity)
    assert before["query_history"]
    _click(app, action)
    assert "uploaded_df" not in app.session_state
    assert app.session_state["uploaded_name"] is None
    assert app.session_state["latest_df"] is None
    assert app.session_state["latest_csv_analysis"] is None
    assert app.session_state["customer_ai_explanation"] is None
    assert app.session_state["messages"] == []
    assert not any(button.label == "Get answer" for button in app.button)
    assert workspace.load_workspace_memory(identity)["query_history"] == before["query_history"]


def test_nonadmin_custom_mapping_includes_returns_and_duplicates(isolated_auth_config, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "")
    upload = BytesIO(
        b"Stock item,Amount charged,Sold on\n"
        b"0007,30.00,05/01/2026\n"
        b"0010,10.00,20/01/2026\n"
        b"0007,18.00,03/02/2026\n"
        b"0007,-6.00,04/02/2026\n"
        b"0007,18.00,03/02/2026\n"
    )
    upload.name = "shop-reconciliation.csv"
    monkeypatch.setattr(st, "file_uploader", lambda *args, **kwargs: upload)
    app = _login(isolated_auth_config, "analyst")
    next(radio for radio in app.radio if radio.label == "Calculate revenue from").set_value("Revenue column").run()
    for label, value in (
        ("Revenue column", "Amount charged"),
        ("Product column", "Stock item"),
        ("Date column", "Sold on"),
        ("Date format", "DD/MM/YYYY"),
        ("Currency for all rows", "CAD"),
    ):
        next(select for select in app.selectbox if select.label == label).set_value(value).run()
        assert not app.exception
    assert any("1 exact duplicate row" in warning.value for warning in app.warning)
    assert any("Negative amounts" in warning.value for warning in app.warning)
    _click(app, "Use this data")
    assert app.session_state["latest_df"].to_dict("records") == [{"revenue": 70.0, "sales_rows": 5}]
    assert app.session_state["latest_csv_analysis"]["currency"] == "CAD"
    _click(app, "Monthly Revenue")
    assert app.session_state["latest_df"].to_dict("records") == [
        {"month": "2026-01", "revenue": 40.0}, {"month": "2026-02", "revenue": 30.0},
    ]
    _click(app, "Revenue by Product")
    assert app.session_state["latest_df"].to_dict("records") == [
        {"product": "0007", "revenue": 60.0}, {"product": "0010", "revenue": 10.0},
    ]
    assert any("Tax, discounts, and shipping are not added or removed" in caption.value for caption in app.caption)
    assert not any(radio.key in {"interface_mode", "top_navigation"} for radio in app.radio)


def test_customer_storage_failure_is_visible_without_connection_details(isolated_auth_config, monkeypatch):
    import workspace

    def unavailable(*args, **kwargs):
        raise PersistenceError("private-connection-details")

    monkeypatch.setattr(workspace, "load_workspace_memory", unavailable)
    app = _login(isolated_auth_config, "analyst")
    assert any("Saved workspace data is temporarily unavailable" in error.value for error in app.error)
    assert not any("private-connection-details" in error.value for error in app.error)
    assert not app.session_state["workspace_loaded"]
    assert not any(button.label == "Try sample data" for button in app.button)


def test_shared_customer_cannot_delete_team_history(isolated_auth_config, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "")
    app = _login(isolated_auth_config, "analyst")
    assert _button(app, "Delete saved workspace data").disabled
    app.radio(key="workspace_scope_choice").set_value("Shared team").run()
    assert not app.exception
    assert not any(button.label == "Delete saved workspace data" for button in app.button)
    assert any("Ask your team administrator" in item.value for item in app.info)


def test_customer_deletes_saved_data_after_explicit_confirmation(isolated_auth_config, monkeypatch):
    import workspace

    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("WORKFLOW_DATABASE_URL", os.environ["DATABASE_URL"])
    app = _login(isolated_auth_config, "analyst")
    _click(app, "Try sample data")
    identity = dict(app.session_state["user_identity"])
    before = workspace.load_workspace_memory(identity)
    assert before["query_history"]
    assert _button(app, "Delete saved workspace data").disabled
    confirmation = next(
        box for box in app.checkbox if box.label == "I understand that saved workspace data will be deleted"
    )
    confirmation.set_value(True).run()
    assert not _button(app, "Delete saved workspace data").disabled
    _click(app, "Delete saved workspace data")

    assert any("Saved workspace data and the active file were deleted" in item.value for item in app.success)
    assert "uploaded_df" not in app.session_state
    assert app.session_state["latest_df"] is None
    assert app.session_state["auth_session"]["user_id"] == "analyst"
    after = workspace.load_workspace_memory(identity)
    assert after["query_history"] == []
    assert after["workflow_runs"] == []
    assert after["_data_generation"] > before.get("_data_generation", 0)
    assert _button(app, "Delete saved workspace data").disabled
    _click(app, "Try sample data")
    assert app.session_state["latest_df"].iloc[0]["revenue"] == 352.0


def test_customer_does_not_claim_deletion_on_storage_failure(isolated_auth_config, monkeypatch):
    import backend.data_lifecycle as lifecycle
    import workspace

    monkeypatch.setenv("OPENAI_API_KEY", "")

    def unavailable(*args, **kwargs):
        raise PersistenceError("private-connection-details")

    monkeypatch.setattr(lifecycle, "delete_workspace_data", unavailable)
    app = _login(isolated_auth_config, "analyst")
    _click(app, "Try sample data")
    identity = dict(app.session_state["user_identity"])
    confirmation = next(
        box for box in app.checkbox if box.label == "I understand that saved workspace data will be deleted"
    )
    confirmation.set_value(True).run()
    _click(app, "Delete saved workspace data")

    assert any("Workspace deletion could not finish" in error.value for error in app.error)
    assert not any("private-connection-details" in error.value for error in app.error)
    assert not any("were deleted" in item.value for item in app.success)
    assert app.session_state["latest_df"] is not None
    assert workspace.load_workspace_memory(identity)["query_history"]
