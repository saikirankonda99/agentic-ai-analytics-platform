# Actual analytics API and worker operations

The main FastAPI application is `backend.main:app`. `POST /execute` queues a real read-only SQL workflow against a server-configured connector. The sales CSV dashboard remains a separate deterministic workflow; CSV rows are not accepted by this endpoint.

## Authenticate and submit

Configure production users with password hashes as described in [Deployment](deployment.md). Authenticate with the configured username and password:

```http
POST /auth/login
Content-Type: application/json

{"username":"YOUR_CONFIGURED_USERNAME","password":"YOUR_CONFIGURED_PASSWORD"}
```

Keep the returned `session.session_token` private. Send it as `X-Session-Token` or `Authorization: Bearer SESSION_TOKEN` on authenticated requests. The OpenAI API key belongs only in the server environment or secret store; clients authenticate with their application session.

```http
POST /execute
X-Session-Token: SESSION_TOKEN
Content-Type: application/json

{
  "question": "What is total revenue by month?",
  "connector_id": "retail",
  "idempotency_key": "monthly-revenue-report-2026-11"
}
```

The authenticated identity supplies the organization, workspace, and user. Request bodies cannot override them or supply a database URL. Administrators and analysts may execute queries; viewers cannot. The connector must grant the exact authenticated organization and workspace access.

`connector_id` defaults to `sqlite`, the explicitly bundled Chinook example. Real customer connectors are configured with `ANALYTICS_CONNECTORS_JSON`, described in [Connectors](connectors.md). A private PostgreSQL connector must use a read-only database account with access limited to the intended customer data. Its configured schema controls schema inspection; database privileges enforce which data its SQL may read.

A successful submission returns HTTP **202** with an explicit `workflow_id`, `execution_mode: "analytics"`, and its current status. A new inline development submission normally returns `queued`; an external worker may already have advanced it. Reusing an idempotency key with the same question and connector returns the same workflow while the retained job exists. Reusing it for a different request returns **409**. Keys are scoped to the authenticated organization, workspace, and user. Once retention or explicit deletion removes a job, its old key no longer deduplicates future requests.

Request limits are 4,000 characters for `question`, 100 for `connector_id`, and 128 for `idempotency_key`. Unknown fields are rejected. Use a fresh idempotency key for a deliberately new analysis.

## Poll status and retrieve output

```http
GET /workflow/WORKFLOW_ID
X-Session-Token: SESSION_TOKEN
```

Status includes `attempts`, `connector_id`, `result_available`, stage information, and measured telemetry. Poll with a modest delay, such as one second. Retrieve the durable result separately:

```http
GET /workflow/WORKFLOW_ID/result
X-Session-Token: SESSION_TOKEN
```

The response contains:

```json
{
  "workflow_id": "workflow:EXAMPLE_ID",
  "status": "completed",
  "attempts": 1,
  "connector_id": "retail",
  "result": {
    "sql": "SELECT SUM(revenue) AS revenue FROM Sales LIMIT 1",
    "columns": ["revenue"],
    "rows": [[352]],
    "error": null,
    "trace": [],
    "telemetry": {}
  },
  "error": null
}
```

The example illustrates the response shape; the actual result also includes schema intelligence, SQL validation, explanations, result quality, and execution diagnostics. `352` is an illustrative synthetic value, not a customer result.

| Status | Meaning |
|---|---|
| `queued` | Persisted and waiting for a worker. |
| `running` | Claimed by a worker with a current lease. |
| `retrying` | A recoverable worker/storage attempt failed; another attempt is scheduled. |
| `completed` | A validated read-only query produced a persisted result. |
| `failed` | Validation, provider access, execution, or worker recovery did not complete successfully. Inspect `error` and any available result diagnostics. |

A model or validation failure can still have a result object containing the failed SQL candidate and diagnostics. Never treat the presence of `result` as proof of successful analytics; require `status == "completed"` and `result.error == null`.

Native JSON values retain their types. Database values outside JSON's native types are stored as strings: notably PostgreSQL `Decimal` values retain their exact decimal text, and dates/timestamps retain their textual representation. Clients should parse these deliberately rather than assuming every numeric-looking value is a floating-point number. Non-finite native floating-point values are rejected during result persistence.

### Usage and costs

`telemetry.usage_source` is `provider` when the pipeline received provider usage, or `unavailable` when it did not. Zero tokens or zero estimated cost with `usage_source: "unavailable"` means measurement is absent; it does not establish that a request was free. Reported costs are estimates, not billing invoices. Queue retries and graph/provider retries are separate mechanisms.

### HTTP errors

| HTTP status | Typical cause |
|---|---|
| `400` | An explicit workflow ID or deletion confirmation is required. |
| `401` | Missing, invalid, expired, or revoked application session. |
| `403` | Insufficient role, workspace ownership, or connector grant. |
| `404` | Unknown connector/workflow, or no actual analytics result for a simulator workflow. |
| `409` | Idempotency conflict or workspace deletion in progress. |
| `422` | Invalid request fields or limits. |
| `429` | The workspace's pending-job capacity is reached; admission includes `Retry-After: 10`. |
| `503` | Analytics admission storage is unavailable, or logout cannot confirm session revocation. |

An accepted job that later loses provider access becomes a failed workflow; it does not return a fabricated result. Retained results require authorization for their original organization and workspace. Session identity is validated server-side; identity headers do not grant access.

## Run the worker

The API and worker must share `WORKFLOW_DATABASE_URL` and the same connector configuration. The application platform database is `DATABASE_URL`. The queue supports SQLite and PostgreSQL; Redis is not required for this worker.

```bash
python -m backend.workers
```

To process at most one available job and exit:

```bash
python -m backend.workers --once
```

Use `ANALYTICS_WORKER_MODE=external` for supervised workers. Production selects this mode by default. Development defaults to `inline`, which drains the newly submitted job after responding; the durable worker command is still needed to recover old jobs after a process restart.

`WORKER_LEASE_SECONDS` defaults to 120. The worker renews its lease while executing. `MAX_PENDING_JOBS_PER_WORKSPACE` defaults to 10. Admission counts queued, running, and retrying jobs. The default queue retry budget is three attempts, including recovered claims; model requests also have their own configured retry policy.

Processing is **at least once**. A crash before the result checkpoint may repeat a read-only query or a paid model request. Once a result is checkpointed, lifecycle projection recovery reuses that result. Lease tokens prevent an expired worker from replacing the durable job result. Idempotency keys deduplicate client submissions, not all possible effects of worker crashes.

The worker stores JSON task data and dispatches only the known analytics task. It does not evaluate supplied Python expressions or load arbitrary task functions.

## Deletion and operator recovery

Workspace deletion blocks new admissions and refuses to proceed while a queued/running/retrying job or direct UI SQL analysis is active. A handled deletion failure keeps admission paused until the user explicitly retries deletion. An unclean process exit during deletion or direct SQL execution can leave a fail-closed marker.

Only after stopping and verifying the relevant original processes, an operator with access to the configured deployment database can clear an abandoned owner marker:

```bash
python -m backend.workers --recover-deletion ORGANIZATION_ID WORKSPACE_ID --confirm-deleter-stopped
```

This does **not** declare deletion complete. Retry the confirmed workspace deletion to finish the purge. For an abandoned direct-analysis marker, stop all analysis processes for that workspace before running:

```bash
python -m backend.workers --recover-activity ORGANIZATION_ID WORKSPACE_ID --confirm-workers-stopped
```

Never clear these markers while the original writer may still be running. The recovery commands log scope identifiers, not credentials. Accounts, sessions, and external backups have separate lifecycles from saved analytics deletion.

## Explicit simulator and streaming boundaries

`POST /execute/simulation` is an administrator-only lifecycle demonstration. It does not call a model or execute SQL, and its responses explicitly identify `execution_mode: "simulation"` and `usage_source: "synthetic"`.

Real jobs are supported through durable status/result polling. Existing replay and SSE endpoints expose persisted snapshots. Existing in-process live websocket broadcasts belong to the simulator runtime; a cross-process analytics event broker consumer is not part of this release.

Automated tests substitute a deterministic provider and execute real read-only SQLite queries. Service integration tests exercise PostgreSQL queue and persistence behavior when `TEST_POSTGRES_URL` is configured. Passing those tests does not establish live model accuracy or validate a customer's real data definition; those remain release checks with the selected deployment and representative business data.
