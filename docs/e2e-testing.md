# Playwright E2E Testing

The E2E suite validates critical Streamlit and FastAPI workflows through a real browser while keeping normal unit tests fast.

## Local Setup

Install Python dependencies and the Chromium browser:

```bash
python -m pip install -r requirements.txt
python -m playwright install chromium
```

Run the E2E suite:

```bash
RUN_E2E=1 python -m pytest tests/e2e
```

On Windows PowerShell:

```powershell
$env:RUN_E2E="1"
python -m pytest tests/e2e
```

## What It Starts

The test fixtures start both services on test ports:

- Streamlit: `http://127.0.0.1:8521`
- FastAPI: `http://127.0.0.1:8021`

The suite uses an isolated SQLite database under `data/test-runtime/` and removes it after the run.

## Coverage

Current browser coverage includes:

- FastAPI `/health` and `/diagnostics` validation before browser workflows depend on the backend.
- successful and failed login flows.
- onboarding rendering, guided query seeding, onboarding dismissal, and persistence after refresh.
- deterministic CSV-backed analytics execution, orchestration completion, result-table rendering, telemetry/observability visibility, CSV export, report export, bookmark saving, and saved report visibility.
- API workspace diagnostics, connector diagnostics, health endpoint visibility, telemetry event search, and workspace report download.
- saved SQL/report/investigation persistence via FastAPI plus browser verification after reload.
- monitoring and operations diagnostics shells, including runtime health, workflow queue, execution graph, and monitoring history.
- optional OpenAI-backed SQL generation, SQL trace visibility, result rendering, bookmarks, and report saving.

OpenAI-backed workflow coverage is marked `openai` and only runs when `OPENAI_API_KEY` is configured.

The default CI suite intentionally uses uploaded CSV data for analytics coverage so deployment validation does not depend on live model credentials. The OpenAI-marked test remains available for environments that want to exercise real SQL generation.

## Test Structure

- `tests/e2e/conftest.py`: service startup, deterministic environment variables, isolated SQLite database, browser context, traces, screenshots, and API request fixtures.
- `tests/e2e/playwright_settings.py`: ports, headless mode, credentials, output directory, and local URLs.
- `tests/e2e/pages.py`: reusable browser helpers for login, navigation, CSV upload, command submission, and API-backed workspace seeding.
- `tests/e2e/test_streamlit_workspace.py`: critical Streamlit and FastAPI workflows.

Custom HTML rendered by the Streamlit UI includes stable `data-testid` attributes derived from section/card titles. Prefer `by_test_id(page, "...")`, roles, labels, placeholders, and download events over timing sleeps or visual snapshots.

## Debugging

Run headed:

```bash
E2E_HEADLESS=false RUN_E2E=1 python -m pytest tests/e2e -q
```

Run a single workflow:

```bash
RUN_E2E=1 python -m pytest tests/e2e/test_streamlit_workspace.py::test_csv_analytics_workflow_exports_reports_and_saved_state -q
```

Artifacts are written to `test-results/playwright`:

- `index.html`: lightweight HTML report
- `logs/`: Streamlit and FastAPI service logs
- `screenshots/`: screenshots on failure
- `traces/`: Playwright traces on failure

View a failure trace with:

```bash
python -m playwright show-trace test-results/playwright/traces/<test-name>.zip
```

If a browser test fails in CI, download the `playwright-artifacts` artifact and inspect `logs/streamlit.log`, `logs/fastapi.log`, the screenshot, and the trace together. The HTML report at `test-results/playwright/index.html` summarizes the tests that ran and their durations.

## CI

GitHub Actions installs Chromium with:

```bash
python -m playwright install --with-deps chromium
```

Then it runs:

```bash
RUN_E2E=1 python -m pytest tests/e2e
```

Artifacts are uploaded on every E2E run so failures can be inspected without rerunning locally.
