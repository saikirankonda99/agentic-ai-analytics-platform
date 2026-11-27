from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest


def _click(app: AppTest, label: str) -> None:
    next(button for button in app.button if button.label == label).click().run()
    assert not app.exception, [item.message for item in app.exception]


def test_sales_demo_results_failure_workspace_switch_and_logout(isolated_auth_config, monkeypatch):
    """Exercise the real Streamlit script without a model or a browser download."""
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("ANONYMIZED_TELEMETRY", "false")
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py", default_timeout=30).run()
    assert not app.exception
    next(field for field in app.text_input if field.label == "Password").set_value(isolated_auth_config["admin"])
    _click(app, "Login")
    assert not any(field.label in {"User", "Team", "Role"} for field in app.text_input)
    app.radio(key="interface_mode").set_value("Admin workspace").run()

    app.radio(key="top_navigation").set_value("Copilot").run()
    assert not app.exception
    _click(app, "Load retail demo")
    assert app.session_state["top_navigation"] == "Overview"
    _click(app, "Revenue by Product")
    result = app.session_state["latest_df"]
    assert dict(zip(result["product"], result["revenue"])) == {"Coffee Beans": 180.0, "Tea": 100.0, "Mug": 72.0}
    assert app.session_state["latest_csv_analysis"]["source_rows"] == 12
    assert "352.00 USD" in app.session_state["latest_insight"]
    assert app.session_state["workflow_telemetry"]["total_tokens"] == 0

    _click(app, "Monthly Revenue")
    result = app.session_state["latest_df"]
    assert dict(zip(result["month"], result["revenue"])) == {"2026-01": 144.0, "2026-02": 117.0, "2026-03": 91.0}

    _click(app, "Revenue by Country")
    result = app.session_state["latest_df"]
    assert dict(zip(result["country"], result["revenue"])) == {"USA": 256.0, "Canada": 74.0, "Germany": 22.0}
    assert app.session_state["command_input"] == "Revenue by country"

    _click(app, "Units Sold by Product")
    result = app.session_state["latest_df"]
    assert dict(zip(result["product"], result["units"])) == {"Coffee Beans": 12.0, "Tea": 10.0, "Mug": 6.0}
    assert app.session_state["command_input"] == "Units sold by product"

    _click(app, "Sales Summary")
    assert app.session_state["latest_df"].to_dict("records") == [{"revenue": 352.0, "sales_rows": 12, "units": 28.0}]
    assert app.session_state["command_input"] == "Sales summary"
    assert app.session_state["workflow_telemetry"]["total_tokens"] == 0

    next(field for field in app.text_input if field.label == "Command").set_value("Predict sales next year as a line chart")
    _click(app, "Run")
    assert app.session_state["latest_df"] is None
    assert app.session_state["latest_csv_analysis"] is None
    assert app.session_state["streaming_workflow"]["status"] == "failed"
    assert app.warning

    _click(app, "Total Revenue")
    assert app.session_state["latest_df"].iloc[0]["revenue"] == 352.0
    app.radio(key="workspace_scope_choice").set_value("Shared team").run()
    assert not app.exception
    assert "uploaded_df" not in app.session_state
    assert app.session_state["latest_df"] is None
    assert app.session_state["latest_insight"] == ""

    _click(app, "Load retail demo")
    _click(app, "Revenue by Product")
    _click(app, "Logout")
    assert "auth_session" not in app.session_state
    assert "uploaded_df" not in app.session_state
    assert app.session_state["latest_df"] is None
    assert app.session_state["messages"] == []
    assert any(field.label == "Password" for field in app.text_input)
