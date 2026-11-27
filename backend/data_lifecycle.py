"""Workspace deletion and scheduled retention for the configured durable stores."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from typing import Any

from backend.config import get_settings
from backend.memory import build_vector_memory_store
from backend.persistence import (
    PersistenceError, WorkspaceDocument, build_workspace_repository,
)
from backend.retention import apply_workspace_retention, retention_days
from backend.storage import PostgreSQLStore, SQLiteStore


_WORKFLOW_TABLES = (
    "workflow_events", "workflow_telemetry", "workflow_agents", "workflow_agent_traces", "usage_records", "workflows",
)


def _workflow_store():
    config = get_settings()
    if config.workflow_database_backend == "postgresql":
        return PostgreSQLStore(config.workflow_database_url), "%s"
    return SQLiteStore(config.sqlite_workflow_path), "?"


def _identity_scope(identity: dict[str, Any]) -> tuple[str, str, str]:
    from workspace import team_workspace_id, workspace_id
    if not identity.get("authenticated"):
        raise PermissionError("Authentication required.")
    team, user, target = (identity.get(name, "") for name in ("team_id", "user_id", "workspace_id"))
    if not team or not user or not target:
        raise PermissionError("An authenticated workspace identity is required.")
    if target != workspace_id(team, user):
        if target != team_workspace_id(team) or identity.get("role") != "admin":
            raise PermissionError("Only the workspace owner or a shared-workspace administrator can delete this data.")
    return f"organization:{team}", target, team


def delete_workspace_data(identity: dict[str, Any]) -> dict[str, int]:
    """Delete this workspace's saved analytics, retaining accounts and login sessions.

    Callers must supply a server-validated identity. A durable admission gate
    prevents queued work from recreating results during the cross-store purge.
    Failure leaves the gate closed; a new explicit delete retries safely.
    """
    from backend.workers import ActiveJobsError, get_worker_queue
    import workspace

    organization_id, target, team = _identity_scope(identity)
    counts: dict[str, int] = {}
    try:
        queue = get_worker_queue()
        with queue.workspace_deletion(organization_id, target):
            counts["jobs"] = queue.delete_workspace_jobs(organization_id, target)
            store, marker = _workflow_store()
            with store._transaction("workspace.delete") as connection:
                for table in _WORKFLOW_TABLES:
                    counts[table] = connection.execute(
                        f"DELETE FROM {table} WHERE organization_id = {marker} AND workspace_id = {marker}",
                        (organization_id, target),
                    ).rowcount
            counts["memory"] = build_vector_memory_store().delete_workspace(
                organization_id=organization_id, workspace_id=target,
            )
            counts["workspace_documents"] = build_workspace_repository().delete(target, team)
            legacy_path = workspace._workspace_path(target)
            if legacy_path.is_symlink():
                raise PersistenceError("Legacy workspace storage needs operator review.")
            counts["legacy_files"] = int(legacy_path.exists())
            legacy_path.unlink(missing_ok=True)
    except ActiveJobsError as exc:
        raise PersistenceError("Wait for active analysis jobs to finish, then try deleting the workspace data again.") from exc
    except PermissionError:
        raise
    except Exception as exc:
        raise PersistenceError(
            "Workspace deletion did not complete. New API jobs remain blocked if deletion started; retry deletion or contact the operator."
        ) from exc
    return counts


def run_retention(*, now: datetime | None = None) -> dict[str, int]:
    """Run from maintenance/cron, including for workspaces nobody opens."""
    from backend.workers import get_worker_queue
    now = now or datetime.now(timezone.utc)
    cutoff = (now - timedelta(days=retention_days("HISTORY_RETENTION_DAYS", 30))).isoformat()
    repository = build_workspace_repository()
    counts = {"workspace_documents": 0, "expired_sessions": 0, "terminal_jobs": 0, "workflows": 0}
    postgres = repository.settings.backend == "postgresql"
    marker = "%s" if postgres else "?"
    with repository.connect() as connection:
        rows = connection.execute("SELECT workspace_id, team_id, memory_json FROM workspace_documents").fetchall()
        counts["expired_sessions"] = connection.execute(
            f"DELETE FROM auth_sessions WHERE expires_at < {marker}", (now.isoformat(),)
        ).rowcount
    for row in rows:
        memory = dict(row["memory_json"]) if isinstance(row["memory_json"], dict) else json.loads(row["memory_json"])
        retained = apply_workspace_retention(memory, now=now)
        if retained != memory:
            changed = repository.replace_if_unchanged(
                WorkspaceDocument(row["workspace_id"], row["team_id"], retained), row["memory_json"],
            )
            counts["workspace_documents"] += int(changed)

    queue = get_worker_queue()
    store, marker = _workflow_store()
    with store._transaction("retention.sweep") as connection:
        # Non-terminal workflows and active jobs are never aged out underneath a worker.
        expired = connection.execute(
            f"SELECT workflow_id, organization_id, workspace_id FROM workflows "
            f"WHERE status IN ('completed','failed','skipped') AND created_at < {marker} "
            "AND workflow_id NOT IN (SELECT workflow_id FROM analytics_jobs WHERE status IN ('queued','running','retrying'))",
            (cutoff,),
        ).fetchall()
        for row in expired:
            for table in _WORKFLOW_TABLES:
                if table == "usage_records":
                    continue
                connection.execute(
                    f"DELETE FROM {table} WHERE workflow_id = {marker} AND organization_id = {marker} AND workspace_id = {marker}",
                    (row["workflow_id"], row["organization_id"], row["workspace_id"]),
                )
            counts["workflows"] += 1
        counts["usage_records"] = connection.execute(
            f"DELETE FROM usage_records WHERE timestamp < {marker}", (cutoff,)
        ).rowcount
    counts["terminal_jobs"] = queue.cleanup_terminal_jobs(cutoff)
    counts["memory"] = build_vector_memory_store().prune_before(cutoff)
    return counts
