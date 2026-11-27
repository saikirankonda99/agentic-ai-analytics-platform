# Deployment

The release stack contains a Streamlit frontend, FastAPI API, a durable analytics worker, a retention service, and PostgreSQL. The API worker runs actual authorized SQL analytics. PostgreSQL also stores customer-scoped query memory; pgvector is optional. Redis is not required for the durable query queue.

## Start the complete stack locally

Install Docker Compose, copy the tracked example configuration to the private local environment file, and configure explicit production users plus a URL-safe `POSTGRES_PASSWORD`. The Compose file runs production mode and does not accept demo accounts.

```bash
cp .env.example .env
docker compose up --build --wait
```

The frontend is at `http://localhost:8501`; the API is at `http://localhost:8000`. Ports bind only to the loopback interface. PostgreSQL has no host port. Use an HTTPS reverse proxy or your hosting provider's HTTPS endpoint when exposing the application.

The backend initializes database schemas, queue and memory before it reports healthy. Frontend, worker and maintenance services depend on that readiness. PostgreSQL schema initialization is serialized across processes by an advisory lock.

The Compose file constructs internal database URLs from the URL-safe password. The platform database is not automatically granted as an analytical customer database. Configure any private customer connectors separately with a read-only role and explicit organization/workspace grants; see [Data isolation](data-isolation.md).

## Accounts

Generate a password hash interactively without placing the password in shell history:

```bash
python -c 'from getpass import getpass; from backend.auth_sessions import hash_password; print(hash_password(getpass("Password: ")))'
```

Use the generated hash in the private environment configuration:

```dotenv
AUTH_USERS='{"owner":{"password_hash":"PASTE_GENERATED_HASH","display_name":"Business Owner","team_id":"my-business","role":"admin"},"analyst":{"password_hash":"ANOTHER_GENERATED_HASH","display_name":"Sales Analyst","team_id":"my-business","role":"analyst"}}'
```

Use a different password for each account. Roles are `admin`, `analyst`, and `viewer`. Account and team identifiers must be canonical, and personal/shared workspace names must not collide. The final username segment `shared` is reserved. Human-readable labels belong in `display_name`.

Existing sessions require a new login after this release if they lack the new configuration fingerprint. Removing an account or changing its password, team, role, or display name invalidates its earlier sessions. Login fails safely when storage is unavailable. A failed logout blocks the browser session behind a retry action until revocation can be confirmed.

## Secret configuration

Supply `OPENAI_API_KEY` only through the server environment or the hosting provider's secret settings. Secure key provisioning is a separate setup step; the repository contains no live key. Local configuration and Streamlit secrets are excluded from Git and Docker build contexts. Provider errors are redacted before logging or storing telemetry. No secret is required for deterministic CSV totals.

The optional CSV AI review submits anonymous calculated statistics and chooses approved fact/action IDs. The SQL workflow sends the requested question and authorized database schema to the provider. Decide whether that use fits the customer's data agreement before enabling its connector.

## Hosted configuration

Deploy the same tested source revision across these processes:

| Process | Image / command | Required durable storage |
|---|---|---|
| Frontend | `Dockerfile.frontend` | `DATABASE_URL`, `WORKFLOW_DATABASE_URL` |
| API | `Dockerfile.backend` | Same URLs |
| Analytics worker | Backend image, `python -m backend.workers` | Same URLs and authorized connector settings |
| Maintenance | Backend image, `python -m backend.maintenance --interval 3600` | Same URLs and optional vector URL |
| Database | PostgreSQL 16 or a compatible validated provider | Persistent provider storage and backups |

All application processes need matching `AUTH_USERS`, `APP_ENV=production`, `STARTUP_VALIDATION_STRICT=true`, `ANALYTICS_WORKER_MODE=external`, and consistent connector configuration. Processes that perform model work need the server-side API key. Set both database URLs explicitly to the same PostgreSQL database unless you have intentionally arranged separate recovery procedures.

For Render, use Docker web services for the frontend/API and a background worker for analytics; maintenance can be a supervised worker or a cron running `python -m backend.maintenance --once`. Review the account's current resource plan and secret configuration before creating services. Render's [Blueprint reference](https://render.com/docs/blueprint-spec) and [environment/secret documentation](https://render.com/docs/configure-environment-variables) describe those provider settings. This repository has not provisioned or updated the existing Render deployment.

The root `render.yaml` and [Render release proposal](render-release.md) prepare a separate paid pilot stack, including its current cost estimate, private secret-entry steps, and preservation of the existing service's local data. Review and approve the provider's concrete plan before applying it.

For an initial Google Cloud operator pilot, follow the [private Compute Engine runbook](google-cloud-pilot.md) and review its [cost proposal](google-cloud-costs.md). This path reuses Docker Compose with IAP access and a dedicated service account for Secret Manager. A public customer HTTPS endpoint, off-server backup scheduling, and hosted acceptance still require separate completion.

The default memory store uses ordinary PostgreSQL. To enable optional pgvector, install the extension administratively and set `VECTOR_DATABASE_URL` to that database. The application does not assume extension-install privileges.

## Verify the deployed revision

1. Record the deployed commit SHA and verify `/health`, `/ready`, and the frontend's `/_stcore/health`.
2. Log in as a non-admin and complete upload, mapping, exact answer, chart, and download. Verify admin controls are absent.
3. Submit a real API question with a workspace-authorized connector, follow the durable workflow ID, and compare SQL/result/usage to the trusted answer. Repeating the same idempotency key must reuse the existing job.
4. Restart the frontend/API/worker and verify saved records and queued work survive.
5. Exercise provider failure and database unavailability without a false success response or legacy file fallback.
6. Run a restore drill into a fresh database and record the result. Keep retention and backup storage scheduled and monitored.
7. Check logs for failures and resource exhaustion, then approve the hosted release.

Application tests, browser tests, container stack checks, and real PostgreSQL service tests are independent evidence. A green build does not prove a hosted site's deployed commit or live model quality. See [Release readiness](release-readiness.md) and [Operations](operations.md).
