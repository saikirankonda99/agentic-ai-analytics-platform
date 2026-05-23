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

- login/authentication
- onboarding controls
- guided query seeding
- API workspace telemetry shell
- workspace report download
- saved SQL/report/investigation persistence via FastAPI plus browser verification
- optional OpenAI-backed SQL generation, result rendering, bookmarks, and report saving

OpenAI-backed workflow coverage is marked `openai` and only runs when `OPENAI_API_KEY` is configured.

## Debugging

Run headed:

```bash
E2E_HEADLESS=false RUN_E2E=1 python -m pytest tests/e2e -q
```

Artifacts are written to `test-results/playwright`:

- `index.html`: lightweight HTML report
- `logs/`: Streamlit and FastAPI service logs
- `screenshots/`: screenshots on failure
- `traces/`: Playwright traces on failure

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
