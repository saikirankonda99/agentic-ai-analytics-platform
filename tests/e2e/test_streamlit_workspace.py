from __future__ import annotations

import csv
import os
import re
from pathlib import Path

import pytest
from playwright.sync_api import expect

from tests.e2e.pages import (
    by_test_id,
    download_full_csv,
    login,
    login_expect_error,
    review_csv_upload,
    run_command,
    seed_workspace_assets,
    select_csv_import_option,
    select_nav,
    upload_csv,
)

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


def test_retail_demo_scroll_and_command_controls_work_at_common_viewports(page, running_services) -> None:
    desktop = {"width": 1366, "height": 768}
    narrow = {"width": 960, "height": 720}
    page.set_viewport_size(desktop)
    login(page, running_services)
    copilot_tab = page.get_by_label("Primary navigation").get_by_text("Copilot", exact=True)
    expect(copilot_tab).to_be_in_viewport(ratio=1)
    copilot_tab.click()
    expect(page.get_by_text("AI Copilot Conversation", exact=True)).to_be_visible()
    page.get_by_role("button", name="Load retail demo", exact=True).click()

    main = page.get_by_test_id("stMain")
    command = page.get_by_placeholder("Ask a revenue, customer, or product question...")
    total_revenue = page.get_by_role("button", name="Total Revenue", exact=True)
    expect(total_revenue).to_be_visible(timeout=20_000)

    # Visibility alone permits off-screen elements. Check the initial viewport
    # before any locator action can automatically scroll the controls into view.
    expect(command).to_be_in_viewport(ratio=1)
    expect(total_revenue).to_be_in_viewport(ratio=1)
    page.screenshot(path=running_services.output_dir / "screenshots" / "retail-demo-desktop.png")

    viewports = (desktop, narrow, {"width": 769, "height": 720}, {"width": 767, "height": 720})
    for index, viewport in enumerate(viewports):
        if index:
            page.set_viewport_size(viewport)
        bounds = main.bounding_box()
        assert bounds is not None
        # Aim at the main panel's edge, away from the separately scrolling sidebar.
        page.mouse.move(bounds["x"] + bounds["width"] - 24, viewport["height"] - 100)
        previous_scroll = main.evaluate("element => element.scrollTop")
        page.mouse.wheel(0, 600)
        page.wait_for_function(
            """previous => {
                const main = document.querySelector('[data-testid="stMain"]');
                return main && main.scrollTop > previous + 1;
            }""",
            arg=previous_scroll,
        )
        page.mouse.wheel(0, -10_000)
        page.wait_for_function(
            """() => {
                const main = document.querySelector('[data-testid="stMain"]');
                return main && main.scrollTop <= 1;
            }"""
        )

        # Smaller windows may need a short wheel movement to expose the button.
        # Keep this a wheel action: scrollIntoView would conceal a broken scroller.
        controls_bottom = total_revenue.evaluate("element => element.getBoundingClientRect().bottom")
        if controls_bottom > viewport["height"]:
            page.mouse.wheel(0, controls_bottom - viewport["height"] + 24)
        expect(command).to_be_in_viewport(ratio=1)
        expect(total_revenue).to_be_in_viewport(ratio=1)
        expect(command).to_be_editable()
        expect(total_revenue).to_be_enabled()
        if viewport == narrow:
            page.screenshot(path=running_services.output_dir / "screenshots" / "retail-demo-narrow.png")


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
    execution_details = page.get_by_test_id("stExpander").filter(
        has=page.get_by_text("Execution details", exact=True)
    )
    execution_details.locator("summary").click()
    expect(execution_details.get_by_text("Workflow completed successfully")).to_be_visible(timeout=30_000)
    expect(by_test_id(page, "observability")).to_be_visible()
    execution_details.locator("summary").click()

    with page.expect_download() as csv_download:
        page.get_by_role("button", name="Download Full CSV").click()
    assert csv_download.value.suggested_filename == "analytics-result.csv"
    with Path(csv_download.value.path()).open(newline="", encoding="utf-8") as source:
        exported = list(csv.DictReader(source))
    assert {row["country"]: float(row["revenue"]) for row in exported} == {"USA": 256, "Canada": 74, "Germany": 22}

    with page.expect_download() as report_download:
        page.get_by_role("button", name="Executive Summary").click()
    assert report_download.value.suggested_filename == "analytics-executive-summary.md"
    report = Path(report_download.value.path()).read_text(encoding="utf-8")
    assert "352.00" in report
    assert "Source sales rows: 12" in report

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


def test_custom_csv_mapping_validates_and_exports_all_sales_rows(logged_in_page, tmp_path, running_services) -> None:
    page = logged_in_page
    sales_csv = tmp_path / "custom-header-sales.csv"
    sales_csv.write_text(
        "Item description,Sold units,Each amount,Sold on\n"
        "Tea,2,15.00,01/05/2026\n"
        "Coffee,1,10.00,01/20/2026\n"
        "Tea,3,6.00,02/03/2026\n",
        encoding="utf-8",
    )
    select_nav(page, "Copilot")
    expect(page.get_by_text("AI Copilot Conversation", exact=True)).to_be_visible()
    review_csv_upload(page, sales_csv)
    by_test_id(page, "csv-import-review").scroll_into_view_if_needed()
    page.screenshot(path=running_services.output_dir / "screenshots" / "csv-import-preview.png")
    expect(page.get_by_role("button", name="Run", exact=True)).to_have_count(0)

    page.get_by_label("Calculate revenue from").get_by_text("Quantity × unit price", exact=True).click()
    quantity_control = page.get_by_test_id("stSelectbox").filter(has=page.get_by_text("Quantity column", exact=True))
    quantity_control.get_by_role("combobox").click()
    quantity_option = page.get_by_role("option", name="Sold units", exact=True)
    expect(quantity_option).to_be_visible()
    page.screenshot(path=running_services.output_dir / "screenshots" / "csv-import-column-options.png")
    quantity_option.click()
    expect(quantity_control.get_by_role("combobox")).to_have_value("Sold units")
    select_csv_import_option(page, "Unit price column", "Each amount")
    select_csv_import_option(page, "Product column", "Item description")
    select_csv_import_option(page, "Date column", "Sold on")
    select_csv_import_option(page, "Date format", "MM/DD/YYYY")
    select_csv_import_option(page, "Currency for all rows", "USD")

    revenue_metric = page.get_by_test_id("stMetric").filter(has=page.get_by_text("Total revenue", exact=True))
    expect(revenue_metric).to_contain_text("58.00 USD")
    expect(page.get_by_text("All 3 rows passed the required checks.", exact=True)).to_be_visible()
    apply_button = page.get_by_role("button", name="Use this data", exact=True)
    expect(apply_button).to_be_enabled()
    apply_button.scroll_into_view_if_needed()
    page.screenshot(path=running_services.output_dir / "screenshots" / "csv-import-review-ready.png")
    apply_button.click()
    expect(page.get_by_text("CSV ready for analysis.", exact=True)).to_be_visible(timeout=20_000)
    expect(by_test_id(page, "csv-import-review")).to_have_count(0)

    run_command(page, "Total revenue")
    expect(by_test_id(page, "sales-summary")).to_contain_text("Total revenue: 58.00 USD.")
    total_rows = download_full_csv(page)
    assert len(total_rows) == 1
    assert float(total_rows[0]["revenue"]) == 58.0

    page.get_by_role("button", name="Monthly Revenue", exact=True).click()
    expect(by_test_id(page, "sales-summary")).to_contain_text("Monthly totals cover 2026-01 through 2026-02")
    months = download_full_csv(page)
    assert {row["month"]: float(row["revenue"]) for row in months} == {"2026-01": 40.0, "2026-02": 18.0}

    page.get_by_role("button", name="Revenue by Product", exact=True).click()
    expect(by_test_id(page, "sales-summary")).to_contain_text("Highest revenue: Tea (48.00).")
    products = download_full_csv(page)
    assert {row["product"]: float(row["revenue"]) for row in products} == {"Tea": 48.0, "Coffee": 10.0}


def test_csv_review_rejects_hidden_bad_row_and_clears_old_results(logged_in_page, tmp_path, running_services) -> None:
    page = logged_in_page
    page.get_by_role("button", name="Load retail demo", exact=True).click()
    run_command(page, "Total revenue")
    expect(by_test_id(page, "sales-summary")).to_contain_text("Total revenue: 352.00 USD.")
    expect(page.get_by_role("button", name="Download Full CSV", exact=True)).to_be_visible()

    invalid_csv = tmp_path / "invalid-after-preview.csv"
    lines = ["product,quantity,unit_price,date,currency"]
    lines.extend(
        f"Item {row},{'not-a-number' if row == 12 else '1'},2.50,2026-01-{row:02d},USD"
        for row in range(1, 13)
    )
    invalid_csv.write_text("\n".join(lines) + "\n", encoding="utf-8")
    review_csv_upload(page, invalid_csv)
    error = page.get_by_text(re.compile(r"Quantity.*data rows:\s*12\b"))
    expect(error).to_be_visible(timeout=20_000)
    expect(page.get_by_role("button", name="Use this data", exact=True)).to_be_disabled()
    expect(page.get_by_role("button", name="Run", exact=True)).to_have_count(0)
    expect(page.get_by_role("button", name="Total Revenue", exact=True)).to_have_count(0)
    expect(page.get_by_placeholder("Ask a revenue, customer, or product question...")).to_have_count(0)
    expect(by_test_id(page, "sales-summary")).to_have_count(0)
    expect(page.get_by_text("Result Explorer", exact=True)).to_have_count(0)
    expect(page.get_by_role("button", name="Download Full CSV", exact=True)).to_have_count(0)
    expect(page.get_by_role("button", name="Executive Summary", exact=True)).to_have_count(0)
    error.scroll_into_view_if_needed()
    page.screenshot(path=running_services.output_dir / "screenshots" / "csv-import-validation-errors.png")

    replacement_csv = tmp_path / "replacement-revenue.csv"
    replacement_csv.write_text("product,revenue,currency\nReplacement,7.50,USD\n", encoding="utf-8")
    review_csv_upload(page, replacement_csv)
    expect(page.get_by_role("radio", name="Revenue column", exact=True)).to_be_checked()
    revenue_control = page.get_by_test_id("stSelectbox").filter(has=page.get_by_text("Revenue column", exact=True))
    expect(revenue_control.get_by_role("combobox")).to_have_value("revenue")
    revenue_metric = page.get_by_test_id("stMetric").filter(has=page.get_by_text("Total revenue", exact=True))
    expect(revenue_metric).to_contain_text("7.50 USD")
    expect(page.get_by_text(re.compile(r"data rows:\s*12\b"))).to_have_count(0)
    expect(page.get_by_role("button", name="Use this data", exact=True)).to_be_enabled()

    page.get_by_role("button", name="Cancel upload", exact=True).click()
    expect(by_test_id(page, "csv-import-review")).to_have_count(0)
    expect(page.get_by_text(re.compile(r"Active data: Chinook example database"))).to_be_visible()
    expect(page.get_by_role("button", name="Run", exact=True)).to_be_enabled()
    expect(page.get_by_role("button", name="Download Full CSV", exact=True)).to_have_count(0)

    review_csv_upload(page, replacement_csv)
    sidebar = page.get_by_test_id("stSidebarUserContent")
    sidebar.get_by_text("Shared team", exact=True).click()
    # The radio changes before the server finishes replacing the workspace uploader.
    expect(by_test_id(page, "enterprise-workspace")).to_contain_text("Workspace scope is team;", timeout=20_000)
    expect(by_test_id(page, "csv-import-review")).to_have_count(0)
    expect(page.get_by_text(re.compile(r"Active data: Chinook example database"))).to_be_visible()
    expect(page.locator("input[type=file]")).to_have_value("")
    expect(page.get_by_role("button", name="Download Full CSV", exact=True)).to_have_count(0)
    expect(page.get_by_role("button", name="Executive Summary", exact=True)).to_have_count(0)

    sidebar.get_by_text("Personal", exact=True).click()
    expect(by_test_id(page, "enterprise-workspace")).to_contain_text("Workspace scope is personal;", timeout=20_000)
    review_csv_upload(page, replacement_csv)
    session_details = sidebar.get_by_test_id("stExpander").filter(has=page.get_by_text("Session", exact=True))
    session_details.locator("summary").click()
    session_details.get_by_role("button", name="Logout", exact=True).click()
    password = page.get_by_role("textbox", name="Password")
    expect(password).to_be_visible()
    expect(by_test_id(page, "csv-import-review")).to_have_count(0)
    expect(page.get_by_text(re.compile(r"Pending data:"))).to_have_count(0)
    expect(page.get_by_role("button", name="Download Full CSV", exact=True)).to_have_count(0)

    # Sign in on the existing page: navigating anew would hide stale session state.
    password.fill(running_services.admin_password)
    page.get_by_role("button", name="Login", exact=True).click()
    expect(page.get_by_text("Quick Actions", exact=True)).to_be_visible(timeout=30_000)
    expect(by_test_id(page, "csv-import-review")).to_have_count(0)
    expect(page.get_by_text(re.compile(r"Active data: Chinook example database"))).to_be_visible()
    expect(page.locator("input[type=file]")).to_have_value("")
    page.get_by_role("button", name="Load retail demo", exact=True).click()
    expect(by_test_id(page, "csv-import-review")).to_have_count(0)
    expect(page.get_by_role("button", name="Total Revenue", exact=True)).to_be_enabled()


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
    execution_details = page.get_by_test_id("stExpander").filter(
        has=page.get_by_text("Execution details", exact=True)
    )
    execution_details.locator("summary").click(timeout=90_000)
    page.get_by_text("SQL Generation").wait_for(timeout=90_000)
    page.get_by_text("Result Explorer").wait_for()
    page.get_by_text("Observability").wait_for()
    execution_details.locator("summary").click()

    page.get_by_role("button", name="Bookmark Query").click()
    page.get_by_text("Query bookmarked.").wait_for()
    page.get_by_role("button", name="Save Report View").click()
    page.get_by_text("Report view saved to this workspace.").wait_for()
