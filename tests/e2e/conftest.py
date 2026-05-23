from __future__ import annotations

import html
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from tests.e2e.playwright_settings import E2ESettings, load_settings


REPORTS: list[dict[str, Any]] = []


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if os.getenv("RUN_E2E", "").strip().lower() in {"1", "true", "yes", "on"}:
        return
    skip = pytest.mark.skip(reason="Playwright E2E tests require RUN_E2E=1")
    for item in items:
        if "e2e" in item.keywords:
            item.add_marker(skip)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo) -> Iterator[None]:
    outcome = yield
    report = outcome.get_result()
    if report.when == "call":
        setattr(item, "e2e_report", report)
        if "e2e" in item.keywords:
            REPORTS.append({"nodeid": item.nodeid, "outcome": report.outcome, "duration": report.duration})


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    output_dir = load_settings().output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = "\n".join(
        "<tr>"
        f"<td>{html.escape(item['nodeid'])}</td>"
        f"<td>{html.escape(item['outcome'])}</td>"
        f"<td>{item['duration']:.2f}s</td>"
        "</tr>"
        for item in REPORTS
    )
    (output_dir / "index.html").write_text(
        f"""
        <!doctype html>
        <html>
        <head><meta charset="utf-8"><title>Playwright E2E Report</title></head>
        <body>
          <h1>Playwright E2E Report</h1>
          <p>Exit status: {exitstatus}</p>
          <table border="1" cellspacing="0" cellpadding="6">
            <thead><tr><th>Test</th><th>Outcome</th><th>Duration</th></tr></thead>
            <tbody>{rows}</tbody>
          </table>
        </body>
        </html>
        """,
        encoding="utf-8",
    )


@pytest.fixture(scope="session")
def e2e_settings() -> E2ESettings:
    settings = load_settings()
    settings.output_dir.mkdir(parents=True, exist_ok=True)
    (settings.output_dir / "logs").mkdir(parents=True, exist_ok=True)
    (settings.output_dir / "screenshots").mkdir(parents=True, exist_ok=True)
    (settings.output_dir / "traces").mkdir(parents=True, exist_ok=True)
    return settings


def _wait_for_url(url: str, timeout_seconds: int = 45) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if 200 <= response.status < 500:
                    return
        except Exception as exc:
            last_error = exc
        time.sleep(0.5)
    raise RuntimeError(f"Timed out waiting for {url}: {last_error}")


def _service_env(settings: E2ESettings) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "APP_ENV": "test",
            "DATABASE_URL": settings.database_url,
            "WORKFLOW_DATABASE_URL": settings.database_url,
            "AUTH_ADMIN_PASSWORD": settings.admin_password,
            "AUTH_ANALYST_PASSWORD": os.getenv("AUTH_ANALYST_PASSWORD", "analyst123"),
            "AUTH_VIEWER_PASSWORD": os.getenv("AUTH_VIEWER_PASSWORD", "viewer123"),
            "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY", ""),
            "STARTUP_VALIDATION_STRICT": "false",
            "STREAMLIT_SERVER_PORT": str(settings.streamlit_port),
        }
    )
    return env


def _start_process(command: list[str], log_path: Path, env: dict[str, str]) -> subprocess.Popen:
    log_file = log_path.open("w", encoding="utf-8")
    return subprocess.Popen(
        command,
        cwd=Path.cwd(),
        env=env,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        text=True,
    )


@pytest.fixture(scope="session")
def running_services(e2e_settings: E2ESettings) -> Iterator[E2ESettings]:
    env = _service_env(e2e_settings)
    fastapi = _start_process(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "backend.main:app",
            "--host",
            e2e_settings.host,
            "--port",
            str(e2e_settings.fastapi_port),
        ],
        e2e_settings.output_dir / "logs" / "fastapi.log",
        env,
    )
    streamlit = _start_process(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            "app.py",
            "--server.headless",
            "true",
            "--server.port",
            str(e2e_settings.streamlit_port),
            "--browser.gatherUsageStats",
            "false",
        ],
        e2e_settings.output_dir / "logs" / "streamlit.log",
        env,
    )
    try:
        _wait_for_url(f"{e2e_settings.fastapi_url}/health")
        _wait_for_url(f"{e2e_settings.streamlit_url}/_stcore/health")
        yield e2e_settings
    finally:
        for process in (streamlit, fastapi):
            process.terminate()
        for process in (streamlit, fastapi):
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
        db_path = Path(e2e_settings.database_url.removeprefix("sqlite:///"))
        for path in (db_path, db_path.with_suffix(".db-shm"), db_path.with_suffix(".db-wal")):
            try:
                path.unlink(missing_ok=True)
            except PermissionError:
                pass
        shutil.rmtree(db_path.parent, ignore_errors=True)


@pytest.fixture(scope="session")
def playwright_instance():
    pytest.importorskip("playwright.sync_api")
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        yield playwright


@pytest.fixture()
def browser_context(playwright_instance, running_services: E2ESettings, request: pytest.FixtureRequest):
    browser = playwright_instance.chromium.launch(headless=running_services.headless)
    context = browser.new_context(accept_downloads=True, base_url=running_services.streamlit_url)
    context.set_default_timeout(running_services.action_timeout_ms)
    context.set_default_navigation_timeout(running_services.navigation_timeout_ms)
    trace_name = request.node.name.replace("/", "_")
    context.tracing.start(screenshots=True, snapshots=True, sources=True)
    try:
        yield context
    finally:
        report = getattr(request.node, "e2e_report", None)
        failed = bool(report and report.failed)
        trace_path = running_services.output_dir / "traces" / f"{trace_name}.zip"
        context.tracing.stop(path=trace_path if failed else None)
        context.close()
        browser.close()


@pytest.fixture()
def page(browser_context, running_services: E2ESettings, request: pytest.FixtureRequest):
    page = browser_context.new_page()
    try:
        yield page
    finally:
        report = getattr(request.node, "e2e_report", None)
        if report and report.failed:
            screenshot_name = request.node.name.replace("/", "_")
            page.screenshot(path=running_services.output_dir / "screenshots" / f"{screenshot_name}.png", full_page=True)


@pytest.fixture()
def logged_in_page(page, running_services: E2ESettings):
    page.goto(running_services.streamlit_url)
    page.get_by_role("textbox", name="Password").fill(running_services.admin_password)
    page.get_by_role("button", name="Login").click()
    page.get_by_text("Agentic analytics command center").wait_for()
    return page


@pytest.fixture()
def api_request(playwright_instance, running_services: E2ESettings):
    request_context = playwright_instance.request.new_context(base_url=running_services.fastapi_url)
    try:
        yield request_context
    finally:
        request_context.dispose()
