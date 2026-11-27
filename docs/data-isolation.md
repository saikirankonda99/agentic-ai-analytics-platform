# Customer data access and memory

## Identity and connector grants

The API derives `organization_id` and `workspace_id` from a validated session. An organization ID is `organization:<team_id>`. Customer SQL execution calls `ConnectorRegistry.get_for_workspace` before inspecting a schema or reading rows. This checks that the connector is enabled and that both the organization and workspace match a server-configured grant. The database helper repeats the check for each operation; result caching cannot bypass revoked access.

The bundled `data/chinook.db` is the explicit public example connector. An unscoped database call can only use this actual bundled file. Changing `SQLITE_DATABASE_PATH` to a private file does not make that file available to every user. An administrator configures ownership and workspace grants for a private connector.

Add private connectors through server environment configuration, never through customer-supplied database URLs:

```json
[
  {
    "connector_id": "store-a-sales",
    "kind": "postgresql",
    "name": "Store A sales",
    "organization_id": "organization:store-a",
    "workspace_ids": ["store-a.owner", "store-a.shared"],
    "dsn_env": "STORE_A_ANALYTICS_DATABASE_URL",
    "schema": "sales"
  }
]
```

Set the JSON as `ANALYTICS_CONNECTORS_JSON`, and store the actual connection secret in the named server environment variable. SQLite definitions use `database_path` instead of `dsn_env`. Connector IDs must be unique; use a new connector ID when replacing its underlying business data source, so SQL examples from the previous source are not reused.

The existing default connectors support `SQLITE_ORGANIZATION_ID` / `SQLITE_WORKSPACE_IDS` and `POSTGRES_ORGANIZATION_ID` / `POSTGRES_WORKSPACE_IDS`. Workspace lists are JSON arrays. A configured private connector without grants is denied. Connector diagnostics redact URL credentials, query parameters and keyword-style DSNs.

Use a dedicated read-only database role with access only to the intended customer's tables. A connector's configured schema guides inspection; it is not a substitute for database permissions or row-level security. SQL guardrails, read-only transactions, query timeouts and result row limits continue to apply. The application does not provision database users or customer row-level policies automatically.

## Persistent memory

Successful SQL examples are keyed and filtered by all of:

- Organization
- Workspace
- Connector ID
- Memory namespace

A call missing any SQL-history scope returns no examples and does not write history. Identical questions from different businesses have different record IDs. General workflow, investigation and insight memories use the same organization/workspace filtering.

The default memory store is a table named `analytics_memory` in `DATABASE_URL`, supporting SQLite and ordinary PostgreSQL. Restarting the app retains these records. Text embeddings use local, deterministic SHA-256 token hashing; they do not send questions to an embedding provider. They provide lexical similarity, not the broader semantic quality of a learned embedding model. The ordinary relational fallback scores up to the 2,000 most recently updated records in the exact scope.

When `VECTOR_DATABASE_URL` is set, `PgVectorMemoryStore` uses `analytics_vector_memory` and PostgreSQL cosine-distance search with organization, workspace, namespace and connector filters in the query. A database administrator must first install the extension:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

The application initializes its table and scope index but does not acquire extension-installation privileges. A missing extension raises an error instead of silently switching to volatile memory. Backup plans must cover both `DATABASE_URL` and a separate `VECTOR_DATABASE_URL` when used.

`delete_workspace(organization_id=..., workspace_id=...)` removes memory for one workspace. `graph.history_store.delete_scope(...)` removes only that workspace's SQL examples. Deletion failures propagate to the caller, so unavailable storage cannot be reported as a successful deletion.

## Legacy history

The former unscoped Chroma collection under `data/history_store` is no longer read or appended to. Its entries cannot be safely assigned to businesses automatically. Operators should inspect ownership offline and remove or archive that old directory according to their data-retention policy. The new workspace deletion operation cannot attribute or remove a particular customer's records from this legacy unscoped directory.

The legacy development aggregate usage log, `data/cost_log.db`, no longer stores or returns question text. Production neither reads nor writes this global log; scoped workflow usage is the production source. Historical files may still contain old question text on disk and require operator retirement alongside old Chroma data. These legacy records are not automatically assigned to a customer or silently erased during startup.

## Verification

`tests/test_data_isolation.py` exercises cross-organization, cross-workspace and cross-connector boundaries, revoked grants, persistence across store instances, scoped deletion, credential redaction and reproducible embeddings across Python hash seeds.

`tests/integration/test_memory_service.py` runs real PostgreSQL and pgvector roundtrip, isolation and deletion checks when `RUN_SERVICE_TESTS=1` and `TEST_POSTGRES_URL` point to a prepared test database. A skipped service test is not evidence of a working PostgreSQL deployment.
