"""The business-owner journey uses a non-admin account and real browser downloads."""
from __future__ import annotations

import csv
from decimal import Decimal
from pathlib import Path

import pytest
from playwright.sync_api import expect

from tests.e2e.pages import (
    _run_and_wait,
    by_test_id,
    login_customer,
    review_csv_upload,
    select_csv_import_option,
)


pytestmark = pytest.mark.e2e


def _download(page, label: str, filename: str) -> Path:
    with page.expect_download() as download_info:
        page.get_by_role("button", name=label, exact=True).click()
    download = download_info.value
    assert download.suggested_filename == filename
    return Path(download.path())


def _download_rows(page) -> list[dict[str, str]]:
    with _download(page, "Download results CSV", "sales-results.csv").open(newline="", encoding="utf-8") as source:
        return list(csv.DictReader(source))


def _open_expander(page, label: str):
    expander = page.get_by_test_id("stExpander").filter(has=page.get_by_text(label, exact=True))
    if expander.locator("details").get_attribute("open") is None:
        expander.locator("summary").click()
    return expander


def _check_wheel_scrolling(page, viewport: dict[str, int]) -> None:
    """Mouse-wheel checks cannot be satisfied by Playwright's automatic scrolling."""
    page.set_viewport_size(viewport)
    main = by_test_id(page, "stMain")
    bounds = main.bounding_box()
    assert bounds is not None
    page.mouse.move(bounds["x"] + bounds["width"] - 24, viewport["height"] - 100)
    page.mouse.wheel(0, -10_000)
    page.wait_for_function("() => document.querySelector('[data-testid=stMain]').scrollTop <= 1")
    page.mouse.wheel(0, 600)
    page.wait_for_function("() => document.querySelector('[data-testid=stMain]').scrollTop > 1")
    page.mouse.wheel(0, 10_000)
    expect(page.get_by_role("button", name="Download results CSV", exact=True)).to_be_in_viewport(ratio=1)
    expect(page.get_by_role("button", name="Download summary", exact=True)).to_be_in_viewport(ratio=1)


def test_nonadmin_customer_maps_reconciles_downloads_and_logs_out(page, running_services, tmp_path) -> None:
    page.set_viewport_size({"width": 1366, "height": 768})
    login_customer(page, running_services)
    sales_csv = tmp_path / "shop-reconciliation.csv"
    sales_csv.write_text(
        "Stock item,Amount charged,Sold on\n"
        "0007,30.00,05/01/2026\n"
        "0010,10.00,20/01/2026\n"
        "0007,18.00,03/02/2026\n"
        "0007,-6.00,04/02/2026\n"
        "0007,18.00,03/02/2026\n",
        encoding="utf-8",
    )
    review_csv_upload(page, sales_csv, customer=True)
    _run_and_wait(
        page,
        lambda: page.get_by_label("Calculate revenue from").get_by_text("Revenue column", exact=True).click(),
    )
    select_csv_import_option(page, "Revenue column", "Amount charged")
    select_csv_import_option(page, "Product column", "Stock item")
    select_csv_import_option(page, "Date column", "Sold on")
    select_csv_import_option(page, "Date format", "DD/MM/YYYY")
    select_csv_import_option(page, "Currency for all rows", "CAD")
    expect(page.get_by_text("All 5 rows passed the required checks.", exact=True)).to_be_visible()
    revenue_metric = page.get_by_test_id("stMetric").filter(has=page.get_by_text("Total revenue", exact=True))
    expect(revenue_metric).to_contain_text("70.00 CAD")
    expect(page.get_by_text("1 exact duplicate row(s) were retained; confirm that they represent separate sales.", exact=True)).to_be_visible()
    _run_and_wait(page, lambda: page.get_by_role("button", name="Use this data", exact=True).click())
    expect(by_test_id(page, "csv-import-review")).to_have_count(0)
    expect(page.get_by_text("Total revenue: 70.00 CAD.", exact=False)).to_be_visible()
    summary_rows = _download_rows(page)
    assert len(summary_rows) == 1
    assert Decimal(summary_rows[0]["revenue"]) == Decimal("70.00")
    assert int(summary_rows[0]["sales_rows"]) == 5

    _open_expander(page, "Common questions")
    _run_and_wait(page, lambda: page.get_by_role("button", name="Monthly Revenue", exact=True).click())
    expect(page.get_by_test_id("stPlotlyChart")).to_be_visible()
    months = _download_rows(page)
    assert {row["month"]: Decimal(row["revenue"]) for row in months} == {
        "2026-01": Decimal("40.00"), "2026-02": Decimal("30.00"),
    }
    _open_expander(page, "Common questions")
    _run_and_wait(page, lambda: page.get_by_role("button", name="Revenue by Product", exact=True).click())
    products = _download_rows(page)
    assert {row["product"]: Decimal(row["revenue"]) for row in products} == {
        "0007": Decimal("60.00"), "0010": Decimal("10.00"),
    }
    report = _download(page, "Download summary", "sales-summary.md").read_text(encoding="utf-8")
    assert "Source rows: 5" in report
    assert "70.00 CAD" in report
    assert "Negative amounts reduce the total" in report
    assert "Exact duplicate rows are retained" in report
    assert "Tax, discounts, and shipping are not added or removed" in report

    for viewport, screenshot_name in (
        ({"width": 1366, "height": 768}, "customer-results-desktop.png"),
        ({"width": 960, "height": 720}, "customer-results-narrow.png"),
    ):
        _check_wheel_scrolling(page, viewport)
        page.screenshot(path=running_services.output_dir / "screenshots" / screenshot_name, full_page=True)
    expect(page.get_by_label("Interface", exact=True)).to_have_count(0)
    expect(page.get_by_label("Primary navigation", exact=True)).to_have_count(0)
    account = _open_expander(page, "Account")
    _run_and_wait(page, lambda: account.get_by_role("button", name="Logout", exact=True).click())
    expect(page.get_by_role("textbox", name="Password", exact=True)).to_be_visible()
    expect(page.get_by_role("button", name="Download results CSV", exact=True)).to_have_count(0)
    # Keep the same page: a fresh browser session could conceal retained data.
    login_customer(page, running_services, navigate=False)
    expect(page.locator("input[type=file]")).to_have_value("")
    expect(page.get_by_role("button", name="Download results CSV", exact=True)).to_have_count(0)
    expect(page.get_by_text(sales_csv.name, exact=False)).to_have_count(0)


def test_nonadmin_customer_removes_active_file_without_deleting_history(page, running_services) -> None:
    login_customer(page, running_services)
    _run_and_wait(page, lambda: page.get_by_role("button", name="Try sample data", exact=True).click())
    expect(page.get_by_role("button", name="Download results CSV", exact=True)).to_be_visible()
    panel = _open_expander(page, "Your sales data · Change file")
    _run_and_wait(page, lambda: panel.get_by_role("button", name="Remove active file", exact=True).click())
    expect(page.get_by_text("Active file and results removed. Saved workspace history is unchanged.", exact=True)).to_be_visible()
    expect(page.get_by_role("button", name="Download results CSV", exact=True)).to_have_count(0)
    expect(page.get_by_role("button", name="Get answer", exact=True)).to_have_count(0)
    expect(page.locator("input[type=file]")).to_have_value("")
    privacy = _open_expander(page, "Data & privacy")
    expect(privacy.get_by_role("button", name="Delete saved workspace data", exact=True)).to_be_disabled()
