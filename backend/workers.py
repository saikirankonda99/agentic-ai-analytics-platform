"""Durable, leased analytics jobs shared by the API and a separate worker process.

The queue uses the workflow database (SQLite locally, PostgreSQL in a hosted stack).
Jobs are at-least-once: a process crash can repeat a read-only query/model request.
Lease tokens fence stale workers from publishing results; request keys deduplicate
client retries. No Python expressions, modules, or arbitrary task names are executed.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import dataclass
from functools import lru_cache
from hashlib import sha256
import json
import os
from pathlib import Path
import sqlite3
import threading
import time
from typing import Any, Iterator
from uuid import uuid4

from backend.config import get_settings
from backend.logging import get_logger

logger = get_logger(__name__)
ACTIVE_STATUSES = ("queued", "running", "retrying")


class QueueCapacityError(ValueError):
    pass


class IdempotencyConflict(ValueError):
    pass


class ActiveJobsError(ValueError):
    pass


@dataclass(frozen=True)
class DurableJob:
    job_id: str
    workflow_id: str
    organization_id: str
    workspace_id: str
    user_id: str
    task_name: str
    payload: dict[str, Any]
    status: str
    attempts: int
    max_attempts: int
    lease_token: str | None
    result: dict[str, Any] | None
    error: str | None


def _job(row: Any) -> DurableJob | None:
    if row is None:
        return None
    return DurableJob(
        job_id=row["job_id"], workflow_id=row["workflow_id"],
        organization_id=row["organization_id"], workspace_id=row["workspace_id"], user_id=row["user_id"],
        task_name=row["task_name"], payload=json.loads(row["payload_json"]), status=row["status"],
        attempts=row["attempts"], max_attempts=row["max_attempts"], lease_token=row["lease_token"],
        result=json.loads(row["result_json"]) if row["result_json"] else None, error=row["error"],
    )


class DurableWorkerQueue:
    def __init__(self, database_url: str, *, lease_seconds: float = 120, max_pending: int = 10) -> None:
        if not database_url.startswith(("sqlite:///", "postgresql://", "postgres://")):
            raise ValueError("A SQLite or PostgreSQL workflow database is required.")
        self.database_url = database_url
        self.postgres = database_url.startswith(("postgresql://", "postgres://"))
        self.lease_seconds = max(float(lease_seconds), 1.0)
        self.max_pending = max(1, int(max_pending))
        if not self.postgres:
            path = Path(database_url.removeprefix("sqlite:///"))
            path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def _sql(self, query: str) -> str:
        return query.replace("?", "%s") if self.postgres else query

    @contextmanager
    def connect(self, *, write: bool = False) -> Iterator[Any]:
        if self.postgres:
            import psycopg
            from psycopg.rows import dict_row
            conn = psycopg.connect(self.database_url, row_factory=dict_row, connect_timeout=10)
        else:
            conn = sqlite3.connect(self.database_url.removeprefix("sqlite:///"), timeout=30)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA busy_timeout=30000")
            if write:
                conn.execute("BEGIN IMMEDIATE")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def initialize(self) -> None:
        with self.connect(write=True) as conn:
            if self.postgres:
                conn.execute("SELECT pg_advisory_xact_lock(846231905)")
            conn.execute("""CREATE TABLE IF NOT EXISTS analytics_jobs (
                job_id TEXT PRIMARY KEY, workflow_id TEXT NOT NULL UNIQUE,
                organization_id TEXT NOT NULL, workspace_id TEXT NOT NULL, user_id TEXT NOT NULL,
                task_name TEXT NOT NULL, payload_json TEXT NOT NULL,
                request_key TEXT NOT NULL UNIQUE, payload_hash TEXT NOT NULL,
                status TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0, max_attempts INTEGER NOT NULL,
                available_at DOUBLE PRECISION NOT NULL, lease_until DOUBLE PRECISION,
                lease_token TEXT, result_json TEXT, error TEXT,
                created_at DOUBLE PRECISION NOT NULL, updated_at DOUBLE PRECISION NOT NULL
            )""")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_analytics_jobs_claim ON analytics_jobs(status, available_at, lease_until)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_analytics_jobs_workspace ON analytics_jobs(organization_id, workspace_id)")
            conn.execute("""CREATE TABLE IF NOT EXISTS analytics_workspace_guards (
                organization_id TEXT NOT NULL, workspace_id TEXT NOT NULL,
                state TEXT NOT NULL, deletion_token TEXT,
                updated_at DOUBLE PRECISION NOT NULL,
                PRIMARY KEY (organization_id, workspace_id)
            )""")
            conn.execute("""CREATE TABLE IF NOT EXISTS analytics_workspace_activity (
                activity_id TEXT PRIMARY KEY, organization_id TEXT NOT NULL,
                workspace_id TEXT NOT NULL, created_at DOUBLE PRECISION NOT NULL
            )""")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_analytics_workspace_activity ON analytics_workspace_activity(organization_id, workspace_id)")

    def enqueue(self, task_name: str, payload: dict[str, Any], *, idempotency_key: str | None = None,
                max_attempts: int = 3) -> str:
        if task_name != "analytics.query":
            raise ValueError("Unknown worker task.")
        for name in ("organization_id", "workspace_id", "user_id", "question", "connector_id"):
            if not isinstance(payload.get(name), str) or not payload[name].strip():
                raise ValueError(f"The job requires {name}.")
        tenant = [payload["organization_id"], payload["workspace_id"], payload["user_id"]]
        request_key = sha256(json.dumps([*tenant, idempotency_key or str(uuid4())]).encode()).hexdigest()
        fingerprint = sha256(json.dumps({k: v for k, v in payload.items() if k != "workflow_id"}, sort_keys=True).encode()).hexdigest()
        now = time.time()
        with self.connect(write=True) as conn:
            if self.postgres:
                # Serialize admission for a workspace, including across API instances.
                lock_id = int.from_bytes(sha256(json.dumps(tenant[:2]).encode()).digest()[:8], "big", signed=True)
                conn.execute("SELECT pg_advisory_xact_lock(%s)", (lock_id,))
            guard = conn.execute(self._sql("SELECT state FROM analytics_workspace_guards WHERE organization_id = ? AND workspace_id = ?"), tuple(tenant[:2])).fetchone()
            if guard is not None and guard["state"] == "deleting":
                raise ActiveJobsError("Workspace deletion is in progress; new analyses are paused.")
            existing = conn.execute(self._sql("SELECT * FROM analytics_jobs WHERE request_key = ?"), (request_key,)).fetchone()
            if existing:
                if existing["payload_hash"] != fingerprint:
                    raise IdempotencyConflict("This request key was already used for a different question or connector.")
                return existing["job_id"]
            pending = conn.execute(self._sql("SELECT COUNT(*) AS count FROM analytics_jobs WHERE organization_id = ? AND workspace_id = ? AND status IN ('queued','running','retrying')"), tuple(tenant[:2])).fetchone()["count"]
            if pending >= self.max_pending:
                raise QueueCapacityError("The workspace already has the maximum number of pending jobs.")
            job_id = f"job:{uuid4()}"
            payload = {**payload, "workflow_id": payload.get("workflow_id") or f"workflow:{uuid4()}"}
            conn.execute(self._sql("""INSERT INTO analytics_jobs
                (job_id, workflow_id, organization_id, workspace_id, user_id, task_name, payload_json,
                 request_key, payload_hash, status, max_attempts, available_at, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'queued', ?, ?, ?, ?)"""),
                (job_id, payload["workflow_id"], *tenant, task_name, json.dumps(payload), request_key,
                 fingerprint, max(1, min(max_attempts, 5)), now, now, now))
        return job_id

    def get(self, job_id: str) -> DurableJob | None:
        with self.connect() as conn:
            return _job(conn.execute(self._sql("SELECT * FROM analytics_jobs WHERE job_id = ?"), (job_id,)).fetchone())

    def for_workflow(self, workflow_id: str) -> DurableJob | None:
        with self.connect() as conn:
            return _job(conn.execute(self._sql("SELECT * FROM analytics_jobs WHERE workflow_id = ?"), (workflow_id,)).fetchone())

    def claim(self, job_id: str | None = None) -> DurableJob | None:
        now = time.time()
        with self.connect(write=True) as conn:
            conn.execute(self._sql("""UPDATE analytics_jobs SET status = 'failed', error = 'Worker recovery attempts exhausted.',
                lease_until = NULL, lease_token = NULL, updated_at = ?
                WHERE status = 'running' AND lease_until < ? AND attempts >= max_attempts"""), (now, now))
            query = """SELECT * FROM analytics_jobs WHERE attempts < max_attempts
                AND ((status IN ('queued','retrying') AND available_at <= ?) OR (status = 'running' AND lease_until < ?))"""
            params: list[Any] = [now, now]
            if job_id:
                query += " AND job_id = ?"
                params.append(job_id)
            query += " ORDER BY created_at LIMIT 1"
            if self.postgres:
                query += " FOR UPDATE SKIP LOCKED"
            row = conn.execute(self._sql(query), tuple(params)).fetchone()
            if row is None:
                return None
            token = str(uuid4())
            conn.execute(self._sql("""UPDATE analytics_jobs SET status = 'running', attempts = attempts + 1,
                lease_token = ?, lease_until = ?, updated_at = ? WHERE job_id = ?"""),
                (token, now + self.lease_seconds, now, row["job_id"]))
            return _job(conn.execute(self._sql("SELECT * FROM analytics_jobs WHERE job_id = ?"), (row["job_id"],)).fetchone())

    def renew(self, job: DurableJob) -> bool:
        now = time.time()
        with self.connect(write=True) as conn:
            cursor = conn.execute(self._sql("""UPDATE analytics_jobs SET lease_until = ?, updated_at = ?
                WHERE job_id = ? AND status = 'running' AND lease_token = ? AND lease_until > ?"""),
                (now + self.lease_seconds, now, job.job_id, job.lease_token, now))
            return cursor.rowcount == 1

    def stage_result(self, job: DurableJob, result: dict[str, Any]) -> bool:
        """Persist output before projecting lifecycle state; recovery can reuse it without another model call."""
        now = time.time()
        with self.connect(write=True) as conn:
            cursor = conn.execute(self._sql("""UPDATE analytics_jobs SET result_json = ?, updated_at = ?
                WHERE job_id = ? AND status = 'running' AND lease_token = ? AND lease_until > ?"""),
                (json.dumps(result, default=str, allow_nan=False), now, job.job_id, job.lease_token, now))
            return cursor.rowcount == 1

    def finish(self, job: DurableJob, *, result: dict[str, Any] | None = None, error: str | None = None,
               retry: bool = False) -> bool:
        now = time.time()
        status = "retrying" if error and retry and job.attempts < job.max_attempts else ("failed" if error else "completed")
        encoded = json.dumps(result, default=str, allow_nan=False) if result is not None else None
        with self.connect(write=True) as conn:
            cursor = conn.execute(self._sql("""UPDATE analytics_jobs SET status = ?, result_json = COALESCE(?, result_json), error = ?,
                available_at = ?, lease_until = NULL, lease_token = NULL, updated_at = ?
                WHERE job_id = ? AND status = 'running' AND lease_token = ? AND lease_until > ?"""),
                (status, encoded, error, now + min(2 ** job.attempts, 60), now, job.job_id, job.lease_token, now))
            return cursor.rowcount == 1

    @contextmanager
    def workspace_activity(self, organization_id: str, workspace_id: str) -> Iterator[None]:
        """Fence synchronous UI analytics against concurrent workspace deletion."""
        scope = (organization_id, workspace_id)
        activity_id = str(uuid4())
        with self.connect(write=True) as conn:
            if self.postgres:
                lock_id = int.from_bytes(sha256(json.dumps(list(scope)).encode()).digest()[:8], "big", signed=True)
                conn.execute("SELECT pg_advisory_xact_lock(%s)", (lock_id,))
            guard = conn.execute(self._sql("SELECT state FROM analytics_workspace_guards WHERE organization_id = ? AND workspace_id = ?"), scope).fetchone()
            if guard and guard["state"] == "deleting":
                raise ActiveJobsError("Workspace deletion is in progress; analysis is paused.")
            conn.execute(self._sql("INSERT INTO analytics_workspace_activity (activity_id, organization_id, workspace_id, created_at) VALUES (?, ?, ?, ?)"),
                         (activity_id, *scope, time.time()))
        try:
            yield
        finally:
            with self.connect(write=True) as conn:
                conn.execute(self._sql("DELETE FROM analytics_workspace_activity WHERE activity_id = ?"), (activity_id,))

    def recover_abandoned_activity(self, organization_id: str, workspace_id: str, *, operator_confirmed_stopped: bool) -> int:
        if not operator_confirmed_stopped:
            raise ValueError("An operator must confirm all workspace analysis processes have stopped.")
        with self.connect(write=True) as conn:
            count = conn.execute(self._sql("DELETE FROM analytics_workspace_activity WHERE organization_id = ? AND workspace_id = ?"), (organization_id, workspace_id)).rowcount
        logger.warning("workspace_activity_recovery_requested organization_id=%s workspace_id=%s", organization_id, workspace_id)
        return count

    @contextmanager
    def workspace_deletion(self, organization_id: str, workspace_id: str) -> Iterator[None]:
        """Block admission across a cross-store purge without holding a database lock.

        A handled failure remains closed but permits an explicit deletion retry.
        A killed process leaves an owned gate: an operator must first confirm the
        original deleter has stopped and run the explicit recovery command.
        """
        token = str(uuid4())
        scope = (organization_id, workspace_id)
        with self.connect(write=True) as conn:
            if self.postgres:
                lock_id = int.from_bytes(sha256(json.dumps(list(scope)).encode()).digest()[:8], "big", signed=True)
                conn.execute("SELECT pg_advisory_xact_lock(%s)", (lock_id,))
            guard = conn.execute(self._sql("SELECT * FROM analytics_workspace_guards WHERE organization_id = ? AND workspace_id = ?"), scope).fetchone()
            if guard and guard["state"] == "deleting" and guard["deletion_token"]:
                raise ActiveJobsError("Another deletion is active or awaiting operator recovery.")
            active = conn.execute(self._sql("SELECT job_id FROM analytics_jobs WHERE organization_id = ? AND workspace_id = ? AND status IN ('queued','running','retrying') LIMIT 1"), scope).fetchone()
            if active:
                raise ActiveJobsError("Wait for active analysis jobs to finish before deleting workspace data.")
            running = conn.execute(self._sql("SELECT activity_id FROM analytics_workspace_activity WHERE organization_id = ? AND workspace_id = ? LIMIT 1"), scope).fetchone()
            if running:
                raise ActiveJobsError("Wait for active workspace analysis to finish before deleting its data.")
            conn.execute(self._sql("""INSERT INTO analytics_workspace_guards (organization_id, workspace_id, state, deletion_token, updated_at)
                VALUES (?, ?, 'deleting', ?, ?) ON CONFLICT (organization_id, workspace_id)
                DO UPDATE SET state = 'deleting', deletion_token = excluded.deletion_token, updated_at = excluded.updated_at"""),
                (*scope, token, time.time()))
        try:
            yield
        except BaseException:
            with self.connect(write=True) as conn:
                conn.execute(self._sql("""UPDATE analytics_workspace_guards SET deletion_token = NULL, updated_at = ?
                    WHERE organization_id = ? AND workspace_id = ? AND deletion_token = ?"""), (time.time(), *scope, token))
            raise
        else:
            with self.connect(write=True) as conn:
                cursor = conn.execute(self._sql("""UPDATE analytics_workspace_guards SET state = 'active', deletion_token = NULL, updated_at = ?
                    WHERE organization_id = ? AND workspace_id = ? AND deletion_token = ?"""), (time.time(), *scope, token))
                if cursor.rowcount != 1:
                    raise ActiveJobsError("The deletion ownership changed; the workspace remains paused.")

    def recover_abandoned_deletion(self, organization_id: str, workspace_id: str, *, operator_confirmed_stopped: bool) -> None:
        if not operator_confirmed_stopped:
            raise ValueError("An operator must confirm the original deletion process has stopped.")
        with self.connect(write=True) as conn:
            conn.execute(self._sql("""UPDATE analytics_workspace_guards SET deletion_token = NULL, updated_at = ?
                WHERE organization_id = ? AND workspace_id = ? AND state = 'deleting'"""),
                (time.time(), organization_id, workspace_id))
        logger.warning("workspace_deletion_recovery_requested organization_id=%s workspace_id=%s", organization_id, workspace_id)

    def delete_workspace_jobs(self, organization_id: str, workspace_id: str) -> int:
        with self.connect(write=True) as conn:
            if self.postgres:
                lock_id = int.from_bytes(sha256(json.dumps([organization_id, workspace_id]).encode()).digest()[:8], "big", signed=True)
                conn.execute("SELECT pg_advisory_xact_lock(%s)", (lock_id,))
            active = conn.execute(self._sql("SELECT job_id FROM analytics_jobs WHERE organization_id = ? AND workspace_id = ? AND status IN ('queued','running','retrying') LIMIT 1"), (organization_id, workspace_id)).fetchone()
            if active:
                raise ActiveJobsError("Wait for active analysis jobs to finish before deleting workspace data.")
            return conn.execute(self._sql("DELETE FROM analytics_jobs WHERE organization_id = ? AND workspace_id = ?"), (organization_id, workspace_id)).rowcount

    def cleanup_terminal_jobs(self, cutoff: str) -> int:
        from datetime import datetime
        timestamp = datetime.fromisoformat(cutoff.replace("Z", "+00:00")).timestamp()
        with self.connect(write=True) as conn:
            return conn.execute(self._sql("DELETE FROM analytics_jobs WHERE status IN ('completed','failed') AND updated_at < ?"), (timestamp,)).rowcount


@lru_cache(maxsize=8)
def _queue(database_url: str, lease_seconds: float, max_pending: int) -> DurableWorkerQueue:
    return DurableWorkerQueue(database_url, lease_seconds=lease_seconds, max_pending=max_pending)


def get_worker_queue() -> DurableWorkerQueue:
    return _queue(get_settings().workflow_database_url, float(os.getenv("WORKER_LEASE_SECONDS", "120")),
                  int(os.getenv("MAX_PENDING_JOBS_PER_WORKSPACE", "10")))


def run_one_job(job_id: str | None = None, *, queue: DurableWorkerQueue | None = None) -> bool:
    """Claim one job. Retry unexpected runtime outages; publish only with a current lease."""
    from backend.services import backend_service, orchestration_service
    queue = queue or get_worker_queue()
    job = queue.claim(job_id)
    if job is None:
        return False
    stopped = threading.Event()

    def heartbeat() -> None:
        while not stopped.wait(max(0.2, queue.lease_seconds / 3)):
            try:
                if not queue.renew(job):
                    return
            except Exception:
                logger.warning("worker_lease_renewal_failed job_id=%s", job.job_id)
                return

    pulse = threading.Thread(target=heartbeat, daemon=True)
    pulse.start()
    try:
        payload = job.payload
        workflow = orchestration_service.get_workflow(job.workflow_id)
        if workflow is None:
            orchestration_service.create_workflow(payload["question"], organization_id=job.organization_id,
                workspace_id=job.workspace_id, user_id=job.user_id, workflow_id=job.workflow_id)
        orchestration_service.start_workflow(job.workflow_id)
        result = job.result
        if result is None:
            result = backend_service.execute_query(payload["question"], organization_id=job.organization_id,
                workspace_id=job.workspace_id, connector_id=payload["connector_id"], callback=lambda *_: None)
        result.setdefault("telemetry", {})["workflow_id"] = job.workflow_id
        error = "Analysis did not complete. Review the validation or provider diagnostics." if result.get("error") else None
        if queue.stage_result(job, result):
            orchestration_service.record_analytics_result(job.workflow_id, result)
            queue.finish(job, result=result, error=error)
    except Exception as exc:
        # Exception text may contain database URLs, provider keys, or query contents.
        logger.warning("worker_job_failed job_id=%s error_type=%s", job.job_id, type(exc).__name__)
        message = "The analysis worker could not complete this attempt."
        if queue.finish(job, error=message, retry=not isinstance(exc, (PermissionError, ValueError))):
            state = queue.get(job.job_id)
            known_result = dict(state.result or {}) if state else {}
            orchestration_service.record_analytics_result(job.workflow_id, {**known_result, "error": message},
                status=state.status if state else "failed")
    finally:
        stopped.set()
        pulse.join(timeout=2)
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the durable analytics worker.")
    parser.add_argument("--once", action="store_true", help="Process at most one available job, then exit.")
    parser.add_argument("--poll-seconds", type=float, default=1.0)
    parser.add_argument("--recover-deletion", nargs=2, metavar=("ORGANIZATION", "WORKSPACE"))
    parser.add_argument("--confirm-deleter-stopped", action="store_true")
    parser.add_argument("--recover-activity", nargs=2, metavar=("ORGANIZATION", "WORKSPACE"))
    parser.add_argument("--confirm-workers-stopped", action="store_true")
    args = parser.parse_args()
    if args.recover_activity:
        if not args.confirm_workers_stopped:
            parser.error("--recover-activity requires --confirm-workers-stopped after stopping all workspace analysis processes")
        get_worker_queue().recover_abandoned_activity(*args.recover_activity, operator_confirmed_stopped=True)
        return
    if args.recover_deletion:
        if not args.confirm_deleter_stopped:
            parser.error("--recover-deletion requires --confirm-deleter-stopped after stopping the original deletion process")
        get_worker_queue().recover_abandoned_deletion(*args.recover_deletion, operator_confirmed_stopped=True)
        return
    while True:
        try:
            processed = run_one_job()
        except Exception as exc:
            logger.warning("worker_poll_failed error_type=%s", type(exc).__name__)
            if args.once:
                raise SystemExit(1) from None
            processed = False
        if args.once:
            return
        if not processed:
            time.sleep(max(0.1, args.poll_seconds))


if __name__ == "__main__":
    main()
