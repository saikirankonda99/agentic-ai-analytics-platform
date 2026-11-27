# Operations, retention and recovery

These commands operate on the configured application databases. Run them from the repository root, using the same Python environment and private server configuration as the deployment. The command-line modules read exported environment variables; merely having an `.env` file beside the repository does not load it into every standalone command. Docker Compose supplies its configured environment to its services.

## Stores to protect

| Configuration | Contents | Backup coverage |
|---|---|---|
| `DATABASE_URL` | Accounts, login sessions, saved workspace documents, deletion generations, and default `analytics_memory` | Always |
| `WORKFLOW_DATABASE_URL` | Workflows, events, telemetry, usage, durable jobs, workspace activity and deletion guards | Always; one snapshot is sufficient when this is the same database as `DATABASE_URL` |
| `VECTOR_DATABASE_URL` | Optional `analytics_vector_memory` pgvector records | Back up separately when configured to a different database |
| Private analytics connectors | Business source databases read by authorized queries | The business/database operator maintains their own backup policy |

Uploaded CSV bytes remain in the active application session; the app does **not** automatically persist the source CSV as a durable file. Saved workspace summaries, queries, reports and metadata can contain business information. A database restore can recover those saved records, but cannot recover an uploaded spreadsheet that was never saved. Keep the original business export in its approved source location.

## Routine retention

The default configuration is:

```dotenv
HISTORY_RETENTION_DAYS=30
SAVED_REPORT_RETENTION_DAYS=90
```

The 30-day policy covers workspace query/workflow history, transcripts, generated insights, telemetry, activity, semantic summaries, eligible completed/failed workflows, terminal jobs, usage records and persistent memory. The 90-day policy covers saved reports, bookmarks and saved or pinned investigations. Expired login sessions are removed according to their actual expiry time. Active, queued and retrying work is not aged out underneath its worker. Each configured retention value must be between 1 and 3,650 days.

Run one sweep:

```bash
python -m backend.maintenance --once
```

A successful one-shot command prints JSON counts and exits with status zero. A failed sweep exits nonzero; investigate and rerun it instead of treating partial cleanup as complete.

Run the supervised maintenance service:

```bash
python -m backend.maintenance --interval 3600
```

The interval is in seconds and must be at least 60. The supplied Compose stack runs this service hourly. It works even when nobody opens a workspace. Old workspace records without usable dates receive a one-time migration timestamp and expire after the configured period; they are not assigned a fresh date on every sweep.

**Retention applies to the live stores. It does not erase backup archives.** Keep backup retention and access controls separately documented, and expire snapshot files together with their `.manifest.json` files. A record deleted today can remain in an older backup until that backup is separately expired.

## Delete one workspace's saved data

Use the authenticated application's **Delete saved workspace data** control and its confirmation. A user can delete their own personal workspace. A shared workspace requires a team administrator. The operation removes saved workspace content, scoped memory, workflow records, usage and terminal jobs, while retaining the account and login sessions. It does not delete a business's source database or the original CSV on their own device.

For an operator-assisted personal-workspace deletion, the following invokes the same service with a validated session. Supply `WORKSPACE_SESSION_TOKEN` through the private operator environment; the command does not print the token or accept caller-invented identity fields:

```bash
python - <<'PY'
import json
import os
from backend.auth_sessions import validate_session_token
from backend.data_lifecycle import delete_workspace_data

identity = validate_session_token(os.environ['WORKSPACE_SESSION_TOKEN'])
if not identity:
    raise SystemExit('A current authenticated workspace session is required.')
print(json.dumps(delete_workspace_data(identity), sort_keys=True))
PY
```

Wait for active analyses to finish before deletion. A durable admission guard prevents new work from recreating records during a purge. A handled failure leaves admission closed and permits an explicit deletion retry. The service reports failure until all configured stores complete their part; a partial purge is not reported as successful.

The platform database retains a `workspace_generations` tombstone. Old browser sessions cannot save their pre-deletion workspace snapshot over the new generation. Do not manually delete or reset this table to clear a UI problem.

## Create and verify a backup

SQLite snapshots use SQLite's online backup API, including committed data in a WAL file. PostgreSQL snapshots use `pg_dump` custom format. Both produce a snapshot plus an adjacent SHA-256 manifest. Snapshot, manifest and restored SQLite files are created with owner-only `0600` permissions on supported POSIX filesystems. They contain private data and are not encrypted by this tool; apply the deployment's encrypted storage and access policy.

PostgreSQL commands require `pg_dump` and `pg_restore` on `PATH`. For the supplied PostgreSQL 16 stack and same-version recovery targets, use PostgreSQL 16 versions of **both** tools. A newer client can produce restore statements unsupported by an older target server, even when creating the dump succeeded. CI explicitly installs PostgreSQL 16 clients, verifies both executable paths and major versions against the server, and fails if a service integration test skips. Ordinary app images may not contain these operator tools. Run the CLI from a trusted maintenance environment with the matching clients and database network access. Credentials are passed through the process environment, not credential-bearing command arguments or printed output.

For a consistent recovery point across **different** databases, stop all application writers before taking the set of snapshots. Each individual online snapshot is consistent on its own; three independently timed snapshots are not an atomic cross-database transaction. With Compose:

```bash
docker compose stop frontend backend worker maintenance
```

Leave PostgreSQL running. In the prepared maintenance environment, make a new snapshot for each distinct configured database:

```bash
backup_stamp=$(date -u +%Y%m%dT%H%M%SZ)
python -m backend.backup create --database-env DATABASE_URL --output "backups/platform-${backup_stamp}.snapshot"
python -m backend.backup create --database-env WORKFLOW_DATABASE_URL --output "backups/workflow-${backup_stamp}.snapshot"
```

Run the second command only when the workflow store is a separate database. If a separate vector database is configured, also run:

```bash
python -m backend.backup create --database-env VECTOR_DATABASE_URL --output "backups/vector-${backup_stamp}.snapshot"
```

Verify each snapshot:

```bash
python -m backend.backup verify --input "backups/platform-${backup_stamp}.snapshot"
```

Repeat verification for the other members of the set. The command checks manifest format, size and SHA-256; SQLite additionally receives an integrity check. It refuses an already existing snapshot destination. A manifest checksum detects accidental modification/corruption; it is not a signature proving the source of an archive. Restore archives produced by the trusted deployment.

After the full set succeeds, restart the services:

```bash
docker compose start backend frontend worker maintenance
```

A verified archive is not yet a completed recovery drill. Periodically restore a selected snapshot set to separate targets and verify actual records and application startup before relying on it.

## Restore into fresh targets

Keep application writers stopped throughout restoration and validation. The tool deliberately does not overwrite a live SQLite database or clean an existing PostgreSQL database.

For SQLite, choose a path that does not already exist:

```bash
python -m backend.backup restore --input backups/platform.snapshot --target recovery/platform.db
python -m backend.backup restore --input backups/workflow.snapshot --target recovery/workflow.db
```

For PostgreSQL, provision an empty target database and place its connection configuration in a private environment variable:

```bash
python -m backend.backup restore --input backups/platform.snapshot --database-env RESTORE_DATABASE_URL
```

Use a separate empty target/environment variable for each separately backed-up workflow or vector store. The restore checks that the PostgreSQL target has no application tables, views or sequences, then uses `pg_restore --single-transaction --exit-on-error`. It never uses `--clean` or drops the target database. Corrupt or mismatched snapshots are refused before restore begins.

Before switching the application to the restored stores:

1. Verify expected rows, reports, totals and schema versions in the new targets.
2. Preserve `workspace_generations` and the workflow deletion/admission guards with the corresponding records. The full database snapshots include them. Never selectively restore only saved workspace documents while discarding their generation tombstones.
3. Reconcile deletion requests made **after** the selected backup. Restoring an older snapshot can reintroduce previously deleted data and older generations; the restore CLI does not automatically replay later deletion requests. Reapply required deletions before reopening access.
4. Select the restored configuration consistently for the frontend, backend, worker and maintenance service. Revoke restored login sessions and require fresh logins, so old recovered tokens cannot silently become active again.
5. Start the services and verify health, customer login, the relevant saved report and worker completion. Retain the old database unchanged until the recovery result is accepted.

After `DATABASE_URL` has explicitly been set to the **restored** platform database, an operator can invalidate its recovered login sessions without printing them:

```bash
python - <<'PY'
from backend.persistence import build_auth_session_repository
build_auth_session_repository().save_sessions({})
print('Restored login sessions revoked; users must sign in again.')
PY
```

## Worker and crash recovery

Production runs the worker as a separate supervised process:

```bash
python -m backend.workers
```

To process at most one available job and exit:

```bash
python -m backend.workers --once
```

The queue persists jobs in `WORKFLOW_DATABASE_URL`. Workers claim jobs using leases and renew them during execution. After a crash, a later worker can reclaim an expired lease within the retry budget. Already persisted results can be reused during lifecycle recovery. An interrupted provider request that completed before its result was durably stored may still need to run again; lease recovery is not a guarantee of exactly one external model charge.

A terminated synchronous UI analysis can leave a workspace activity record. Stop all analysis processes for the workspace before using the explicit operator recovery command:

```bash
python -m backend.workers --recover-activity 'organization:store-a' 'store-a.owner' --confirm-workers-stopped
```

A killed workspace-deletion process can leave an owned deletion guard. First confirm that the original deleting process is stopped, then release only its abandoned ownership:

```bash
python -m backend.workers --recover-deletion 'organization:store-a' 'store-a.owner' --confirm-deleter-stopped
```

Use the actual organization/workspace IDs from the authenticated deployment. These flags are operator confirmations of processes already stopped; they do not stop those processes themselves. Deletion recovery does **not** finish the purge or reopen admission. Retry the authorized workspace deletion to complete all stores and reopen the workspace. Do not clear guards while another process is still working.

## Legacy artifacts

The unscoped Chroma history and legacy cost database have been removed from the new Git tree. Existing local files and historical Git commits can still retain those artifacts; removing a tracked path does not rewrite history or erase another checkout.

The current application does not read the old unscoped Chroma history. The development cost log no longer stores or returns question text, and production does not use that global log. Review and retire existing `data/history_store` and `data/cost_log.db` files under the operator's retention policy. Their old records cannot be safely assigned to an individual workspace automatically, so workspace deletion cannot promise to remove a customer's contribution from these legacy artifacts.

## Verification scope

The repository includes SQLite recovery tests and gated real PostgreSQL backup/restore, deletion-generation and read-only connector tests. Live service tests require `RUN_SERVICE_TESTS=1`, `TEST_POSTGRES_URL`, compatible PostgreSQL clients and an isolated test service allowed to create disposable databases/roles. A skipped test is not a successful recovery drill. These operational commands do not establish that a public deployment or live AI integration has been verified.
