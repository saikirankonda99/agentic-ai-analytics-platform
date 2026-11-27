from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from csv_analytics import DEMO_PATH


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
