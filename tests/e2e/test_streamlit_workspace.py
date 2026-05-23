from __future__ import annotations

import os

import pytest


pytestmark = pytest.mark.e2e


def select_nav(page, label: str) -> None:
    page.get_by_text(label, exact=True).click()


def test_login_onboarding_and_guided_query_seed(logged_in_page) -> None:
    page = logged_in_page

    page.get_by_text("Workspace Onboarding").wait_for()
    page.get_by_role("button", name="Use sample dataset").click()
    page.get_by_text("Sample dataset is ready.").wait_for()
    page.get_by_role("button", name="Try guided query").click()

    page.get_by_text("Command Workspace").wait_for()
    page.get_by_placeholder("Ask a revenue, customer, or product question...").wait_for()


def test_api_workspace_exports_and_telemetry_shell(logged_in_page) -> None:
    page = logged_in_page

    select_nav(page, "API")
    page.get_by_text("API Runtime Diagnostics").wait_for()
    page.get_by_text("Workspace Inspection").wait_for()
    page.get_by_text("Telemetry Event Search").wait_for()

    with page.expect_download() as download_info:
        page.get_by_role("button", name="Export Workspace Report").click()
    download = download_info.value
    assert download.suggested_filename == "workspace-report.json"


def test_workspace_history_restores_saved_assets(api_request, logged_in_page, running_services) -> None:
    login = api_request.post(
        "/auth/login",
        data={"username": running_services.admin_username, "password": running_services.admin_password},
    )
    assert login.ok
    session = login.json()["session"]
    headers = {"X-Session-Token": session["session_token"]}
    workspace_id = session["workspace_id"]

    saved_sql = api_request.post(
        f"/workspace/{workspace_id}/sql-history",
        data={"question": "List customers", "sql": "select 1", "rows": 1},
        headers=headers,
    )
    saved_investigation = api_request.post(
        f"/workspace/{workspace_id}/investigations",
        data={"investigation": {"status": "completed", "summary": "Found anomaly"}, "note": "E2E"},
        headers=headers,
    )
    saved_report = api_request.post(
        f"/workspace/{workspace_id}/reports",
        data={"title": "E2E executive summary", "scope": "analytics", "summary": "Healthy", "payload": {"rows": 1}},
        headers=headers,
    )

    assert saved_sql.ok
    assert saved_investigation.ok
    assert saved_report.ok

    page = logged_in_page
    page.reload()
    page.get_by_role("textbox", name="Password").fill(running_services.admin_password)
    page.get_by_role("button", name="Login").click()
    page.get_by_text("Agentic analytics command center").wait_for()
    select_nav(page, "History")
    page.get_by_text("Saved Query History").wait_for()
    page.get_by_text("List customers", exact=True).wait_for()
    page.get_by_text("Saved Report Views").wait_for()
    page.get_by_text("E2E executive summary").first.wait_for()

    select_nav(page, "Investigations")
    page.get_by_text("Investigation Sessions").wait_for()
    page.get_by_text("Found anomaly", exact=True).first.wait_for()


@pytest.mark.openai
@pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="SQL generation E2E requires OPENAI_API_KEY")
def test_query_execution_sql_generation_and_bookmark_flow(logged_in_page) -> None:
    page = logged_in_page

    page.get_by_role("button", name="Revenue by Country").first.click()
    page.get_by_text("SQL Generation", timeout=90_000).wait_for()
    page.get_by_text("Result Explorer").wait_for()
    page.get_by_text("Observability").wait_for()

    page.get_by_role("button", name="Bookmark Query").click()
    page.get_by_text("Query bookmarked.").wait_for()
    page.get_by_role("button", name="Save Report View").click()
    page.get_by_text("Report view saved to this workspace.").wait_for()
