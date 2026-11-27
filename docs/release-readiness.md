# End-to-end release readiness

This is a release-candidate checklist for the current branch. A claim of complete hosted delivery requires every acceptance gate below; code presence alone is insufficient.

## Product scope

The first release supports customer sales CSV analysis, six exact report types, charts and downloads, an optional bounded AI review, a separate admin workspace, and authenticated natural-language SQL analytics against configured read-only connectors. It includes durable API jobs, workspace-scoped persistence, retention/deletion, and recovery tooling.

Scheduled accounting-system ingestion, automatic customer business actions, self-service billing, and cross-process live websocket streaming are outside this release. Administrator monitoring checks remain page-driven. API job status/results are durable and polled; SSE/replay is a snapshot and live simulation broadcasts are explicitly separate.

## Implementation and acceptance gates

| Area | Implemented behavior | Acceptance gate |
|---|---|---|
| Customer UI | Upload/review, exact totals, chart, export, non-admin access, active-file removal | AppTests plus real browser journey on the release revision |
| Sales accounting | Explicit dates/currency, line rounding, returns/duplicates retained with warnings | Reconcile one real business export against its trusted report |
| AI review | Anonymous aggregate facts, validated fact/action selections, safe failure | Successful live provider response and observed latency/usage |
| SQL/API | Real authenticated SQL generation/validation/read-only execution and durable results | Real provider golden evaluation plus hosted API run |
| Jobs | SQLite/PostgreSQL queue, leases/fencing, bounded retries, idempotency, checkpoints | Service-backed worker restart/concurrency verification |
| Isolation | Connector grants and database-level permissions; memory scoped by org/workspace/connector | Cross-workspace tests and actual read-only PostgreSQL role test |
| Accounts | Canonical IDs, configuration-bound expiring sessions, role checks, confirmed logout | Account-change, revocation, outage and browser tests |
| Persistence | Durable stores; production failure blocks instead of falling back to JSON | PostgreSQL service tests and deployed restart check |
| Lifecycle | Explicit workspace deletion, stale-session guards, retention maintenance | Deletion/activity concurrency tests and scheduled sweep verification |
| Recovery | Verified SQLite snapshots and PostgreSQL custom archives; fresh-target restore | Real PostgreSQL backup/restore drill and hosted backup policy |
| Secrets | Server-only configuration; ignored local files; Docker exclusions; redacted diagnostics | Key securely available to the intended runtime, never in source/screenshots |
| Deployment | Complete Docker stack, non-root images, startup validation and loopback ports | Hosted revision, HTTPS, non-admin journey and operator review |

## Automated evidence

Platform CI runs lint, application tests, startup checks, customer/admin Playwright E2E, backend/frontend image builds plus a complete stack smoke check, and real PostgreSQL/pgvector/backup/connector tests. The stack smoke deliberately has no API key and confirms missing credentials produce a real failure instead of fabricated results. Deterministic fake-provider tests execute real SQLite SQL and verify exact outputs; they are not live model evaluations.

Validation results and the exact tested commit are recorded in the pull request and GitHub Actions. The local environment uses the locked packages on Python 3.12; CI verifies the supported Python 3.11 runtime. Local Chromium download is blocked, so browser verification must come from the hosted CI run.

## Remaining external gates

- Make the securely created API key available to the intended runtime through a confirmed secret destination. The coding workspace has no configured key; no live model request has been made in this release work.
- Run the selected model's golden SQL evaluation and bounded CSV AI review, inspect incorrect answers, and record actual usage/cost.
- Connect or configure the hosting account and deploy the reviewed revision, with explicit production accounts and persistent storage.
- Verify the hosted customer/admin/API journeys and restart/recovery behavior.
- Obtain and reconcile one representative real-business export; document the owner's accepted revenue convention and measurable feedback.

These gates require account access, the provider credential, or business evidence. Synthetic sample totals are demonstration results and must not be presented as customer impact.
