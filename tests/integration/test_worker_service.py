"""Real PostgreSQL queue checks; supplied only by the service integration CI job."""
from __future__ import annotations

import os
from uuid import uuid4

import pytest

from backend.workers import ActiveJobsError, DurableWorkerQueue


@pytest.mark.skipif(not os.getenv("TEST_POSTGRES_URL"), reason="TEST_POSTGRES_URL is not configured")
def test_postgresql_durable_queue_claim_and_workspace_guard():
    url = os.environ["TEST_POSTGRES_URL"]
    queue = DurableWorkerQueue(url, lease_seconds=60)
    scope = (f"organization:queue-{uuid4()}", f"workspace:{uuid4()}")
    payload = {"question": "SELECT-only test", "connector_id": "fixture", "organization_id": scope[0],
               "workspace_id": scope[1], "user_id": "test-user"}
    job_id = queue.enqueue("analytics.query", payload, idempotency_key="one")
    assert DurableWorkerQueue(url).enqueue("analytics.query", payload, idempotency_key="one") == job_id
    claimed = queue.claim(job_id)
    assert claimed and claimed.attempts == 1
    assert DurableWorkerQueue(url).claim(job_id) is None
    assert queue.renew(claimed)
    assert queue.finish(claimed, result={"columns": ["total"], "rows": [[352]]})
    assert DurableWorkerQueue(url).get(job_id).result["rows"] == [[352]]
    with queue.workspace_deletion(*scope):
        with pytest.raises(ActiveJobsError):
            DurableWorkerQueue(url).enqueue("analytics.query", payload)
        assert queue.delete_workspace_jobs(*scope) == 1
    assert queue.get(job_id) is None
