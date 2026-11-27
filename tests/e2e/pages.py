from __future__ import annotations

import csv
import os
import re
from collections.abc import Callable
from pathlib import Path

from playwright.sync_api import APIRequestContext, Page, TimeoutError as PlaywrightTimeoutError, expect

from tests.e2e.playwright_settings import E2ESettings


_CURRENT_ELEMENT = (
    '[data-testid="stElementContainer"][data-stale="false"]'
    ':not([data-retained="true"])'
)


def by_test_id(page: Page, value: str):
    return page.locator(f'[data-testid="{value}"]')


def _wait_for_streamlit_idle(page: Page) -> None:
    expect(by_test_id(page, "stApp")).to_have_attribute(
        "data-test-script-state", "notRunning", timeout=30_000,
    )
    expect(page.locator('[data-testid="stElementContainer"][data-stale="true"]')).to_have_count(
        0, timeout=30_000,
    )


def _run_and_wait(page: Page, action: Callable[[], None]) -> None:
    """Observe a server round trip, not just an optimistic widget value update."""
    _wait_for_streamlit_idle(page)
    tracker = page.evaluate_handle(
        """() => {
            const app = document.querySelector('[data-testid="stApp"]');
            const busy = state => state === 'running' || state === 'rerunRequested';
            const tracker = {sawRunning: false, completed: false, observer: null};
            tracker.observer = new MutationObserver(records => {
                const state = app.getAttribute('data-test-script-state');
                // oldValue also catches a complete run batched into one callback.
                tracker.sawRunning ||= busy(state) || records.some(record => busy(record.oldValue));
                tracker.completed = tracker.sawRunning && state === 'notRunning';
            });
            tracker.observer.observe(app, {
                attributes: true,
                attributeOldValue: true,
                attributeFilter: ['data-test-script-state'],
            });
            return tracker;
        }""",
    )
    try:
        action()
        page.wait_for_function("tracker => tracker.completed", arg=tracker, timeout=30_000)
        _wait_for_streamlit_idle(page)
    finally:
        tracker.evaluate("tracker => tracker.observer.disconnect()")
        tracker.dispose()


def select_admin_workspace(page: Page) -> None:
    """Select operator tools after login has rendered the customer interface."""
    interface = page.locator(_CURRENT_ELEMENT).get_by_label("Interface", exact=True)
    admin_radio = interface.get_by_role("radio", name="Admin workspace", exact=True)
    expect(admin_radio).to_be_attached(timeout=30_000)
    _wait_for_streamlit_idle(page)
    if not admin_radio.is_checked():
        _run_and_wait(page, lambda: interface.get_by_text("Admin workspace", exact=True).click())
    expect(admin_radio).to_be_checked()
    expect(page.get_by_text("Quick Actions", exact=True)).to_be_visible(timeout=30_000)
    _wait_for_streamlit_idle(page)


def login(page: Page, settings: E2ESettings, password: str | None = None) -> None:
    page.goto(settings.streamlit_url)
    password_box = page.get_by_role("textbox", name="Password")
    try:
        expect(password_box).to_be_visible(timeout=15_000)
        password_box.fill(password or settings.admin_password)
        page.get_by_role("button", name="Login").click()
    except (AssertionError, PlaywrightTimeoutError):
        pass
    # Existing end-to-end scenarios exercise operator tools. Customer mode is
    # now the default, and only authenticated admins can select this workspace.
    select_admin_workspace(page)


def login_expect_error(page: Page, settings: E2ESettings, password: str) -> None:
    page.goto(settings.streamlit_url)
    page.get_by_role("textbox", name="Password").fill(password)
    page.get_by_role("button", name="Login").click()
    expect(page.get_by_text("Invalid credentials")).to_be_visible()


def login_customer(page: Page, settings: E2ESettings, *, navigate: bool = True) -> None:
    """Sign in as a real non-admin; do not select or fall back to operator tools."""
    if navigate:
        page.goto(settings.streamlit_url)
    page.get_by_role("textbox", name="Username", exact=True).fill("analyst")
    page.get_by_role("textbox", name="Password", exact=True).fill(os.getenv("AUTH_ANALYST_PASSWORD", "analyst123"))
    _run_and_wait(page, lambda: page.get_by_role("button", name="Login", exact=True).click())
    expect(page.get_by_role("button", name="Try sample data", exact=True)).to_be_visible()
    expect(page.get_by_label("Interface", exact=True)).to_have_count(0)
    expect(page.get_by_label("Primary navigation", exact=True)).to_have_count(0)


def select_nav(page: Page, label: str) -> None:
    page.get_by_label("Primary navigation").get_by_text(label, exact=True).click()


def review_csv_upload(page: Page, csv_path: Path, *, customer: bool = False) -> None:
    _wait_for_streamlit_idle(page)
    uploader = by_test_id(page, "stMain" if customer else "stSidebarUserContent").locator(
        f'{_CURRENT_ELEMENT} [data-testid="stFileUploaderDropzoneInput"]',
    )
    expect(uploader).to_have_count(1)
    expect(uploader).to_be_enabled()
    _run_and_wait(page, lambda: uploader.set_input_files(str(csv_path)))
    expect(by_test_id(page, "csv-import-review")).to_be_visible(timeout=20_000)
    expect(page.get_by_text(re.compile(rf"^File: {re.escape(csv_path.name)} ·"))).to_be_visible(timeout=20_000)
    _wait_for_streamlit_idle(page)


def upload_csv(page: Page, csv_path: Path) -> None:
    """Review and accept a fixture whose standard sales headers map automatically."""
    review_csv_upload(page, csv_path)
    apply_button = page.get_by_role("button", name="Use this data", exact=True)
    expect(apply_button).to_be_enabled()
    _run_and_wait(page, apply_button.click)
    expect(page.get_by_text("CSV ready for analysis.", exact=True)).to_be_visible(timeout=20_000)
    expect(by_test_id(page, "csv-import-review")).to_have_count(0)


def select_csv_import_option(
    page: Page, label: str, option: str, *, screenshot_path: Path | None = None,
) -> None:
    control = page.locator(f'{_CURRENT_ELEMENT} [data-testid="stSelectbox"]').filter(
        has=page.get_by_text(label, exact=True),
    )
    combobox = control.get_by_role("combobox")
    expect(combobox).to_have_count(1)
    expect(combobox).to_be_enabled()
    _wait_for_streamlit_idle(page)
    # Streamlit does not request another run when the value is unchanged.
    if combobox.input_value() == option:
        expect(combobox).to_have_value(option)
        return
    # The explicit trigger focuses before opening; clicking the input can open
    # on pointerdown and then close again when focus scrolls a low control.
    control.scroll_into_view_if_needed()
    control.get_by_role("button", name="Open", exact=True).click()
    expect(combobox).to_have_attribute("aria-expanded", "true")
    selected_option = page.get_by_role("option", name=option, exact=True)
    expect(selected_option).to_be_visible()
    if screenshot_path is not None:
        page.screenshot(path=screenshot_path)
    _run_and_wait(page, selected_option.click)
    expect(combobox).to_have_value(option)


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
