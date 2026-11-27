from __future__ import annotations

from datetime import datetime, timezone

import pytest

import backend.workers as workers
from backend.workers import ActiveJobsError, DurableWorkerQueue, IdempotencyConflict, QueueCapacityError


def payload(**overrides):
    return {"question": "What is total revenue?", "connector_id": "retail", "organization_id": "organization:test",
            "workspace_id": "test.analyst", "user_id": "analyst", **overrides}


def test_restart_claim_recovery_and_fencing(tmp_path, monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(workers.time, "time", lambda: clock[0])
    url = f"sqlite:///{tmp_path / 'queue.db'}"
    queue = DurableWorkerQueue(url, lease_seconds=10)
    job_id = queue.enqueue("analytics.query", payload())
    first = queue.claim()
    assert first.job_id == job_id
    reopened = DurableWorkerQueue(url, lease_seconds=10)
    assert reopened.claim() is None
    clock[0] += 11
    recovered = reopened.claim()
    assert recovered.attempts == 2
    assert recovered.lease_token != first.lease_token
    assert queue.finish(first, result={"rows": [[999]]}) is False
    assert reopened.finish(recovered, result={"columns": ["revenue"], "rows": [[352]]}) is True
    assert DurableWorkerQueue(url).get(job_id).result["rows"] == [[352]]
    assert reopened.claim() is None


def test_request_keys_are_tenant_scoped_and_detect_mismatched_payload(tmp_path):
    queue = DurableWorkerQueue(f"sqlite:///{tmp_path / 'queue.db'}")
    job_id = queue.enqueue("analytics.query", payload(), idempotency_key="retry-this")
    assert queue.enqueue("analytics.query", payload(), idempotency_key="retry-this") == job_id
    with pytest.raises(IdempotencyConflict):
        queue.enqueue("analytics.query", payload(question="Different question"), idempotency_key="retry-this")
    other = queue.enqueue("analytics.query", payload(organization_id="organization:other", workspace_id="other.analyst"), idempotency_key="retry-this")
    assert other != job_id


def test_bounded_retries_and_terminal_cleanup(tmp_path, monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(workers.time, "time", lambda: clock[0])
    queue = DurableWorkerQueue(f"sqlite:///{tmp_path / 'queue.db'}")
    job_id = queue.enqueue("analytics.query", payload(), max_attempts=2)
    first = queue.claim()
    queue.finish(first, error="Temporary outage", retry=True)
    assert queue.get(job_id).status == "retrying"
    assert queue.claim() is None
    clock[0] += 3
    second = queue.claim()
    queue.finish(second, error="Temporary outage", retry=True)
    assert queue.get(job_id).status == "failed"
    pending = queue.enqueue("analytics.query", payload())
    assert queue.cleanup_terminal_jobs(datetime.fromtimestamp(1004, timezone.utc).isoformat()) == 1
    assert queue.get(job_id) is None
    assert queue.get(pending).status == "queued"


def test_queue_limits_and_expired_last_attempt(tmp_path, monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(workers.time, "time", lambda: clock[0])
    queue = DurableWorkerQueue(f"sqlite:///{tmp_path / 'queue.db'}", lease_seconds=2, max_pending=1)
    job_id = queue.enqueue("analytics.query", payload(), max_attempts=1)
    with pytest.raises(QueueCapacityError):
        queue.enqueue("analytics.query", payload())
    queue.claim()
    clock[0] += 3
    assert queue.claim() is None
    assert queue.get(job_id).status == "failed"


def test_deletion_is_blocked_by_jobs_and_direct_queries(tmp_path):
    queue = DurableWorkerQueue(f"sqlite:///{tmp_path / 'queue.db'}")
    scope = ("organization:test", "test.analyst")
    with queue.workspace_activity(*scope):
        with pytest.raises(ActiveJobsError):
            with queue.workspace_deletion(*scope):
                pytest.fail("An active direct query must block deletion")
    job_id = queue.enqueue("analytics.query", payload())
    with pytest.raises(ActiveJobsError):
        with queue.workspace_deletion(*scope):
            pytest.fail("Queued jobs must block deletion")
    claimed = queue.claim(job_id)
    queue.finish(claimed, result={"rows": [[1]]})
    with queue.workspace_deletion(*scope):
        with pytest.raises(ActiveJobsError):
            queue.enqueue("analytics.query", payload())
        with pytest.raises(ActiveJobsError):
            with queue.workspace_activity(*scope):
                pytest.fail("A new direct query must not enter a deletion")
        assert queue.delete_workspace_jobs(*scope) == 1
    assert queue.get(job_id) is None
    assert queue.enqueue("analytics.query", payload())


def test_failed_deletion_remains_closed_until_explicit_retry(tmp_path):
    queue = DurableWorkerQueue(f"sqlite:///{tmp_path / 'queue.db'}")
    scope = ("organization:test", "test.analyst")
    with pytest.raises(RuntimeError):
        with queue.workspace_deletion(*scope):
            raise RuntimeError("A later persistence store was unavailable")
    with pytest.raises(ActiveJobsError):
        queue.enqueue("analytics.query", payload())
    with queue.workspace_deletion(*scope):
        pass
    assert queue.enqueue("analytics.query", payload())


def test_worker_cannot_execute_arbitrary_task_names(tmp_path):
    queue = DurableWorkerQueue(f"sqlite:///{tmp_path / 'queue.db'}")
    with pytest.raises(ValueError, match="Unknown worker task"):
        queue.enqueue("os.system", payload())


def test_json_result_preserves_decimal_precision_and_timestamp(tmp_path):
    from decimal import Decimal
    queue = DurableWorkerQueue(f"sqlite:///{tmp_path / 'queue.db'}")
    job_id = queue.enqueue("analytics.query", payload())
    job = queue.claim(job_id)
    timestamp = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    assert queue.finish(job, result={"rows": [[Decimal("123456789012345678.01"), timestamp]]})
    restored = DurableWorkerQueue(queue.database_url).get(job_id).result["rows"][0]
    assert restored[0] == "123456789012345678.01"
    assert datetime.fromisoformat(restored[1]) == timestamp


def test_atomic_sqlite_workflow_creation_never_resets_later_state(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from dataclasses import replace
    from backend.models import OrchestrationExecution, WorkflowTelemetry
    from backend.storage import SQLiteWorkflowStorage
    path = tmp_path / "workflow.db"
    first_store = SQLiteWorkflowStorage(path)
    second_store = SQLiteWorkflowStorage(path)
    workflow = OrchestrationExecution(workflow_id="workflow:race", workspace_id="test.admin", question="Total revenue",
                                      status="queued", created_at=datetime.now(timezone.utc).isoformat(), telemetry=WorkflowTelemetry())
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda store: store.create_if_absent(workflow), (first_store, second_store)))
    assert sorted(outcomes) == [False, True]
    first_store.save(replace(workflow, status="completed"))
    assert second_store.create_if_absent(workflow) is False
    assert second_store.get(workflow.workflow_id).status == "completed"
