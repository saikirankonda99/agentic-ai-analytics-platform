from __future__ import annotations

import csv
import re
from pathlib import Path

from playwright.sync_api import APIRequestContext, Page, TimeoutError as PlaywrightTimeoutError, expect

from tests.e2e.playwright_settings import E2ESettings


def by_test_id(page: Page, value: str):
    return page.locator(f'[data-testid="{value}"]')


def login(page: Page, settings: E2ESettings, password: str | None = None) -> None:
    page.goto(settings.streamlit_url)
    password_box = page.get_by_role("textbox", name="Password")
    try:
        expect(password_box).to_be_visible(timeout=15_000)
        password_box.fill(password or settings.admin_password)
        page.get_by_role("button", name="Login").click()
    except (AssertionError, PlaywrightTimeoutError):
        pass
    expect(page.get_by_text("Quick Actions")).to_be_visible(timeout=30_000)


def login_expect_error(page: Page, settings: E2ESettings, password: str) -> None:
    page.goto(settings.streamlit_url)
    page.get_by_role("textbox", name="Password").fill(password)
    page.get_by_role("button", name="Login").click()
    expect(page.get_by_text("Invalid credentials")).to_be_visible()


def select_nav(page: Page, label: str) -> None:
    page.get_by_label("Primary navigation").get_by_text(label, exact=True).click()


def review_csv_upload(page: Page, csv_path: Path) -> None:
    page.locator("input[type=file]").set_input_files(str(csv_path))
    expect(by_test_id(page, "csv-import-review")).to_be_visible(timeout=20_000)
    expect(page.get_by_text(re.compile(rf"^File: {re.escape(csv_path.name)} ·"))).to_be_visible(timeout=20_000)


def upload_csv(page: Page, csv_path: Path) -> None:
    """Review and accept a fixture whose standard sales headers map automatically."""
    review_csv_upload(page, csv_path)
    apply_button = page.get_by_role("button", name="Use this data", exact=True)
    expect(apply_button).to_be_enabled()
    apply_button.click()
    expect(page.get_by_text("CSV ready for analysis.", exact=True)).to_be_visible(timeout=20_000)
    expect(by_test_id(page, "csv-import-review")).to_have_count(0)


def select_csv_import_option(page: Page, label: str, option: str) -> None:
    control = page.get_by_test_id("stSelectbox").filter(has=page.get_by_text(label, exact=True))
    control.get_by_role("combobox").click()
    page.get_by_role("option", name=option, exact=True).click()
    expect(control.get_by_text(option, exact=True)).to_be_visible()


def download_full_csv(page: Page) -> list[dict[str, str]]:
    with page.expect_download() as download_info:
        page.get_by_role("button", name="Download Full CSV", exact=True).click()
    download = download_info.value
    assert download.suggested_filename == "analytics-result.csv"
    with Path(download.path()).open(newline="", encoding="utf-8") as source:
        return list(csv.DictReader(source))


def run_command(page: Page, question: str) -> None:
    page.get_by_placeholder("Ask a revenue, customer, or product question...").fill(question)
    page.get_by_role("button", name="Run").click()


def seed_workspace_assets(api_request: APIRequestContext, settings: E2ESettings) -> None:
    login_response = api_request.post(
        "/auth/login",
        data={"username": settings.admin_username, "password": settings.admin_password},
    )
    assert login_response.ok
    session = login_response.json()["session"]
    headers = {"X-Session-Token": session["session_token"]}
    workspace_id = session["workspace_id"]

    assert api_request.post(
        f"/workspace/{workspace_id}/sql-history",
        data={"question": "List customers", "sql": "select 1", "rows": 1},
        headers=headers,
    ).ok
    assert api_request.post(
        f"/workspace/{workspace_id}/investigations",
        data={"investigation": {"status": "completed", "summary": "Found anomaly"}, "note": "E2E"},
        headers=headers,
    ).ok
    assert api_request.post(
        f"/workspace/{workspace_id}/reports",
        data={"title": "E2E executive summary", "scope": "analytics", "summary": "Healthy", "payload": {"rows": 1}},
        headers=headers,
    ).ok
