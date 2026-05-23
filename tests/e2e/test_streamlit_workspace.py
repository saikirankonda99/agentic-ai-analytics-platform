from __future__ import annotations

import os

import pytest
from playwright.sync_api import expect

from tests.e2e.pages import by_test_id, login, login_expect_error, run_command, seed_workspace_assets, select_nav, upload_csv

pytestmark = pytest.mark.e2e


def test_fastapi_health_and_diagnostics(api_request) -> None:
    health = api_request.get("/health")
    diagnostics = api_request.get("/diagnostics")

    assert health.ok
    assert health.json()["status"] == "ok"
    assert diagnostics.ok
    assert "startup" in diagnostics.json()


def test_invalid_login_renders_graceful_error(page, running_services) -> None:
    login_expect_error(page, running_services, "wrong-password")


def test_login_onboarding_and_guided_query_seed(logged_in_page) -> None:
    page = logged_in_page

    expect(by_test_id(page, "workspace-onboarding")).to_be_visible()
    page.get_by_role("button", name="Use sample dataset").click()
    expect(page.get_by_text("Sample dataset is ready.")).to_be_visible()
    page.get_by_role("button", name="Try guided query").click()

    expect(by_test_id(page, "command-workspace")).to_be_visible()
    expect(page.get_by_placeholder("Ask a revenue, customer, or product question...")).to_be_visible()


def test_onboarding_dismissal_persists_after_refresh(logged_in_page, running_services) -> None:
    page = logged_in_page

    expect(by_test_id(page, "workspace-onboarding")).to_be_visible()
    page.get_by_role("button", name="Hide guide").click()
    expect(by_test_id(page, "workspace-onboarding")).not_to_be_visible(timeout=10_000)
    page.reload()
    login(page, running_services)
    expect(by_test_id(page, "workspace-onboarding")).not_to_be_visible()


def test_csv_analytics_workflow_exports_reports_and_saved_state(logged_in_page, sample_csv) -> None:
    page = logged_in_page

    upload_csv(page, sample_csv)
    run_command(page, "Summarize uploaded revenue by country")

    expect(page.get_by_text("Result Explorer")).to_be_visible(timeout=60_000)
    expect(page.get_by_text("Showing 3 of 3 rows.")).to_be_visible()
    expect(page.get_by_text("Workflow completed successfully")).to_be_visible(timeout=30_000)
    expect(by_test_id(page, "observability")).to_be_visible()

    with page.expect_download() as csv_download:
        page.get_by_role("button", name="Download Full CSV").click()
    assert csv_download.value.suggested_filename == "analytics-result.csv"

    with page.expect_download() as report_download:
        page.get_by_role("button", name="Executive Summary").click()
    assert report_download.value.suggested_filename == "analytics-executive-summary.md"

    page.get_by_role("button", name="Bookmark Query").click()
    expect(page.get_by_text("Query bookmarked.")).to_be_visible()
    page.get_by_role("button", name="Save Report View").click()
    expect(page.get_by_text("Report view saved to this workspace.")).to_be_visible()
    page.get_by_role("button", name="Share Report").click()
    expect(page.get_by_text("Report shared with this workspace.")).to_be_visible()

    select_nav(page, "History")
    expect(by_test_id(page, "saved-query-history")).to_be_visible()
    expect(by_test_id(page, "saved-query-history").get_by_text("Summarize uploaded revenue by country")).to_be_visible()
    expect(by_test_id(page, "saved-report-views")).to_be_visible()
    expect(by_test_id(page, "saved-report-views").get_by_text("Shared")).to_be_visible()
    expect(by_test_id(page, "performance-diagnostics")).to_be_visible()


def test_api_workspace_exports_and_telemetry_shell(logged_in_page) -> None:
    page = logged_in_page

    select_nav(page, "API")
    expect(by_test_id(page, "api-runtime-diagnostics")).to_be_visible()
    expect(by_test_id(page, "connector-diagnostics")).to_be_visible()
    expect(by_test_id(page, "workspace-inspection")).to_be_visible()
    expect(by_test_id(page, "telemetry-event-search")).to_be_visible()
    expect(page.get_by_text("GET /health")).to_be_visible()

    with page.expect_download() as download_info:
        page.get_by_role("button", name="Export Workspace Report").click()
    download = download_info.value
    assert download.suggested_filename == "workspace-report.json"


def test_workspace_history_restores_saved_assets(api_request, logged_in_page, running_services) -> None:
    seed_workspace_assets(api_request, running_services)

    page = logged_in_page
    page.reload()
    login(page, running_services)
    select_nav(page, "History")
    expect(by_test_id(page, "saved-query-history")).to_be_visible()
    expect(page.get_by_text("List customers", exact=True)).to_be_visible()
    expect(by_test_id(page, "saved-report-views")).to_be_visible()
    expect(page.get_by_text("E2E executive summary").first).to_be_visible()

    select_nav(page, "Investigations")
    expect(by_test_id(page, "investigation-sessions")).to_be_visible()
    expect(by_test_id(page, "investigation-sessions").get_by_text("Found anomaly")).to_be_visible()


def test_workspace_scope_switching_is_stable(logged_in_page) -> None:
    page = logged_in_page

    sidebar = page.get_by_test_id("stSidebarUserContent")
    sidebar.get_by_text("Shared team").click()
    select_nav(page, "History")
    expect(by_test_id(page, "workspace-continuity")).to_be_visible(timeout=20_000)
    expect(by_test_id(page, "performance-diagnostics")).to_be_visible()

    sidebar.get_by_text("Personal").click()
    select_nav(page, "Overview")
    expect(by_test_id(page, "command-workspace")).to_be_visible(timeout=20_000)


def test_monitoring_and_operations_diagnostics_shell(logged_in_page) -> None:
    page = logged_in_page

    page.get_by_test_id("stSidebarUserContent").get_by_text("Scheduled Monitoring").click()
    page.get_by_role("button", name="Run scheduled check").click()
    select_nav(page, "Monitoring")
    expect(by_test_id(page, "monitoring-run-history")).to_be_visible(timeout=60_000)

    select_nav(page, "Operations")
    expect(by_test_id(page, "runtime-health")).to_be_visible()
    expect(by_test_id(page, "workflow-queue")).to_be_visible()


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
