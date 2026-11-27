from __future__ import annotations

import sqlite3

from fastapi.testclient import TestClient
import pytest


@pytest.fixture
def analytics_client(isolated_auth_config, tmp_path, monkeypatch):
    import backend.connectors as connectors
    import backend.routes as routes
    import backend.services as services
    import backend.workers as workers
    import graph.workflow as graph
    from backend.main import app
    from backend.memory import InMemoryVectorMemoryStore
    from backend.storage import (
        InMemoryAccountStorage, InMemoryWorkflowStorage, InMemoryEventStorage,
        InMemoryTelemetryStorage, InMemoryAgentExecutionStorage, InMemoryAgentTraceStorage, InMemoryUsageStorage,
    )
    path = tmp_path / "sales.db"
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE Sales (revenue INTEGER)")
        conn.executemany("INSERT INTO Sales VALUES (?)", [(180,), (100,), (72,)])
    registry = connectors.ConnectorRegistry({
        "sqlite": connectors.SQLiteConnector(connectors.SQLiteConnectorConfig()),
        "retail": connectors.SQLiteConnector(connectors.SQLiteConnectorConfig(
            connector_id="retail", database_path=str(path), organization_id="organization:default-team",
            workspace_ids=("default-team.admin",),
        )),
        "other-business": connectors.SQLiteConnector(connectors.SQLiteConnectorConfig(
            connector_id="other-business", database_path=str(path), organization_id="organization:other",
            workspace_ids=("other.admin",),
        )),
    })
    monkeypatch.setattr(connectors, "connector_registry", registry)
    monkeypatch.setenv("WORKFLOW_DATABASE_URL", f"sqlite:///{tmp_path / 'jobs.db'}")
    monkeypatch.setenv("ANALYTICS_WORKER_MODE", "inline")
    queue = workers.get_worker_queue()
    lifecycle = services.OrchestrationService(
        workflow_storage=InMemoryWorkflowStorage(), account_storage=InMemoryAccountStorage(),
        event_storage=InMemoryEventStorage(), telemetry_storage=InMemoryTelemetryStorage(),
        agent_execution_storage=InMemoryAgentExecutionStorage(), agent_trace_storage=InMemoryAgentTraceStorage(),
        usage_storage=InMemoryUsageStorage(), vector_memory_store=InMemoryVectorMemoryStore(), connector_registry=registry,
    )
    backend = services.AnalyticsBackendService()
    monkeypatch.setattr(services, "backend_service", backend)
    monkeypatch.setattr(services, "orchestration_service", lifecycle)
    monkeypatch.setattr(routes, "backend_service", backend)
    monkeypatch.setattr(routes, "orchestration_service", lifecycle)
    calls = []
    state = {"sql": "SELECT SUM(revenue) AS revenue FROM Sales LIMIT 1", "usage": True}

    def model(question, schema, model=graph.DEFAULT_SQL_MODEL, token_callback=None):
        calls.append({"question": question, "schema": schema})
        usage = {"prompt_tokens": 8, "completion_tokens": 7, "total_tokens": 15, "cost_usd": 0.001} if state["usage"] else {}
        return {"sql": state["sql"], "telemetry": {"model": model, "latency_ms": 2,
                "usage_available": state["usage"], **usage}}

    monkeypatch.setattr(graph, "stream_sql_with_telemetry", model)
    monkeypatch.setattr(graph, "generate_sql_with_telemetry", model)
    monkeypatch.setattr(graph, "retrieve_similar_queries", lambda *args, **kwargs: [])
    monkeypatch.setattr(graph, "save_query_to_history", lambda *args, **kwargs: None)
    monkeypatch.setattr(graph, "log_query_cost", lambda *args, **kwargs: None)
    with TestClient(app) as client:
        login = client.post("/auth/login", json={"username": "admin", "password": isolated_auth_config["admin"]})
        assert login.status_code == 200
        client.headers["X-Session-Token"] = login.json()["session"]["session_token"]
        yield client, queue, calls, state, path, lifecycle


def test_actual_api_runs_sql_and_persists_measured_result(analytics_client):
    client, queue, calls, _, _, _ = analytics_client
    created = client.post("/execute", json={"question": "What is total revenue?", "connector_id": "retail", "idempotency_key": "retail-report"})
    assert created.status_code == 202, created.text
    payload = created.json()
    assert payload["execution_mode"] == "analytics"
    assert payload["status"] == "queued"
    assert payload["telemetry"]["usage_source"] == "unavailable"
    workflow_id = payload["workflow_id"]
    status = client.get(f"/workflow/{workflow_id}").json()
    result = client.get(f"/workflow/{workflow_id}/result").json()
    assert status["status"] == "completed"
    assert status["telemetry"]["usage_source"] == "provider"
    assert status["telemetry"]["token_usage"]["total_tokens"] == 15
    assert result["result"]["columns"] == ["revenue"]
    assert result["result"]["rows"] == [[352]]
    assert "Sales" in calls[0]["schema"]
    assert len(calls) == 1
    assert queue.for_workflow(workflow_id).result["rows"] == [[352]]
    # A duplicate HTTP submission returns the same durable result without a second model request.
    duplicate = client.post("/execute", json={"question": "What is total revenue?", "connector_id": "retail", "idempotency_key": "retail-report"})
    assert duplicate.json()["workflow_id"] == workflow_id
    assert len(calls) == 1
    assert client.get(f"/workflow/{workflow_id}/execution-graph").status_code == 200


def test_unknown_usage_is_never_replaced_with_synthetic_tokens(analytics_client):
    client, _, _, state, _, _ = analytics_client
    state["usage"] = False
    workflow_id = client.post("/execute", json={"question": "Total revenue", "connector_id": "retail"}).json()["workflow_id"]
    telemetry = client.get(f"/workflow/{workflow_id}/telemetry").json()
    assert telemetry["usage_source"] == "unavailable"
    assert telemetry["token_usage"]["total_tokens"] == 0
    assert telemetry["estimated_cost_usd"] == 0


def test_real_pipeline_rejects_destructive_model_sql(analytics_client):
    client, _, _, state, path, _ = analytics_client
    state["sql"] = "DELETE FROM Sales"
    workflow_id = client.post("/execute", json={"question": "Total revenue", "connector_id": "retail"}).json()["workflow_id"]
    result = client.get(f"/workflow/{workflow_id}/result").json()
    assert result["status"] == "failed"
    assert result["result"]["error"]
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT SUM(revenue) FROM Sales").fetchone() == (352,)


def test_customer_connector_authorization_happens_before_model_call(analytics_client):
    client, _, calls, _, _, _ = analytics_client
    assert client.post("/execute", json={"question": "Total revenue", "connector_id": "other-business"}).status_code == 403
    assert calls == []
    configs = client.get("/connectors").json()["connectors"]
    assert {item["connector_id"] for item in configs} == {"sqlite", "retail"}
    for suffix in ("schema", "health", "validate"):
        method = client.post if suffix == "validate" else client.get
        assert method(f"/connectors/other-business/{suffix}").status_code == 403
    diagnostics = client.get("/diagnostics").json()
    assert "other-business" not in str(diagnostics)


def test_results_require_the_same_workspace_and_viewer_cannot_execute(analytics_client, isolated_auth_config):
    client, _, _, _, _, _ = analytics_client
    workflow_id = client.post("/execute", json={"question": "Total revenue", "connector_id": "retail"}).json()["workflow_id"]
    viewer = client.post("/auth/login", json={"username": "viewer", "password": isolated_auth_config["viewer"]}).json()["session"]["session_token"]
    headers = {"X-Session-Token": viewer}
    assert client.get(f"/workflow/{workflow_id}/result", headers=headers).status_code == 403
    assert client.post("/execute", json={"question": "Total revenue"}, headers=headers).status_code == 403


def test_external_worker_recovers_submissions_without_background_tasks(analytics_client, monkeypatch):
    from backend.workers import DurableWorkerQueue, run_one_job
    client, queue, calls, _, _, _ = analytics_client
    monkeypatch.setenv("ANALYTICS_WORKER_MODE", "external")
    workflow_id = client.post("/execute", json={"question": "Total revenue", "connector_id": "retail"}).json()["workflow_id"]
    assert client.get(f"/workflow/{workflow_id}").json()["status"] == "queued"
    assert calls == []
    reopened = DurableWorkerQueue(queue.database_url)
    assert run_one_job(queue=reopened) is True
    assert client.get(f"/workflow/{workflow_id}/result").json()["result"]["rows"] == [[352]]


def test_worker_reauthorizes_connector_after_queued_grant_is_revoked(analytics_client, monkeypatch):
    import backend.connectors as connectors
    from backend.workers import run_one_job
    client, queue, calls, _, path, _ = analytics_client
    monkeypatch.setenv("ANALYTICS_WORKER_MODE", "external")
    workflow_id = client.post("/execute", json={"question": "Total revenue", "connector_id": "retail"}).json()["workflow_id"]
    registry = connectors.get_connector_registry()
    registry._connectors["retail"] = connectors.SQLiteConnector(connectors.SQLiteConnectorConfig(
        connector_id="retail", database_path=str(path), organization_id="organization:other",
        workspace_ids=("other.admin",),
    ))
    assert run_one_job(queue=queue)
    assert calls == []
    assert client.get(f"/workflow/{workflow_id}/result").json()["status"] == "failed"


def test_recovery_reuses_a_persisted_result_after_lifecycle_projection_failure(analytics_client, monkeypatch):
    import backend.workers as workers
    client, queue, calls, _, _, lifecycle = analytics_client
    monkeypatch.setenv("ANALYTICS_WORKER_MODE", "external")
    workflow_id = client.post("/execute", json={"question": "Total revenue", "connector_id": "retail"}).json()["workflow_id"]
    original = lifecycle.record_analytics_result
    failures = [True]

    def temporary_failure(*args, **kwargs):
        if failures[0]:
            failures[0] = False
            raise RuntimeError("Transient lifecycle storage outage")
        return original(*args, **kwargs)

    monkeypatch.setattr(lifecycle, "record_analytics_result", temporary_failure)
    assert workers.run_one_job(queue=queue)
    job = queue.for_workflow(workflow_id)
    assert job.status == "retrying"
    assert job.result["rows"] == [[352]]
    # Make the deterministic retry immediately eligible without sleeping.
    with queue.connect(write=True) as conn:
        conn.execute("UPDATE analytics_jobs SET available_at = 0 WHERE job_id = ?", (job.job_id,))
    assert workers.run_one_job(queue=queue)
    assert client.get(f"/workflow/{workflow_id}/result").json()["status"] == "completed"
    assert len(calls) == 1


def test_external_worker_can_finish_during_admission_without_state_reset(analytics_client, monkeypatch):
    from backend.workers import run_one_job
    client, queue, calls, _, _, lifecycle = analytics_client
    monkeypatch.setenv("ANALYTICS_WORKER_MODE", "external")
    create = lifecycle.workflow_storage.create_if_absent
    started = [False]

    def worker_wins_first_insert(workflow):
        # Force the exact interleaving: API observed no row, but the worker
        # creates and completes it before the API's initial insert reaches SQL.
        if not started[0]:
            started[0] = True
            assert run_one_job(queue=queue)
        return create(workflow)

    monkeypatch.setattr(lifecycle.workflow_storage, "create_if_absent", worker_wins_first_insert)
    submitted = client.post("/execute", json={"question": "Total revenue", "connector_id": "retail"})
    assert submitted.status_code == 202, submitted.text
    workflow_id = submitted.json()["workflow_id"]
    stored = lifecycle.get_workflow(workflow_id)
    assert stored.status == "completed"
    assert stored.telemetry.token_usage.total_tokens == 15
    assert stored.stage_progression
    assert len(calls) == 1
    assert client.get(f"/workflow/{workflow_id}/result").json()["result"]["rows"] == [[352]]


def test_logout_does_not_claim_revocation_when_storage_is_unavailable(analytics_client, monkeypatch):
    import backend.routes as routes
    from backend.persistence import PersistenceError
    client, _, _, _, _, _ = analytics_client

    def unavailable(token):
        raise PersistenceError("Session store unavailable")

    monkeypatch.setattr(routes, "revoke_session_checked", unavailable)
    response = client.post("/auth/logout", json={"session_token": "an-existing-session"})
    assert response.status_code == 503
    assert "revoked" not in response.json()


def test_projection_retry_does_not_duplicate_observed_usage(analytics_client, monkeypatch):
    import backend.workers as workers
    client, queue, _, _, _, lifecycle = analytics_client
    monkeypatch.setenv("ANALYTICS_WORKER_MODE", "external")
    workflow_id = client.post("/execute", json={"question": "Total revenue", "connector_id": "retail"}).json()["workflow_id"]
    append = lifecycle.usage_service.usage_storage.append
    should_fail = [True]

    def fail_after_token_record(usage):
        if usage.event_type == "estimated_ai_cost" and should_fail[0]:
            should_fail[0] = False
            raise RuntimeError("Temporary usage storage failure")
        append(usage)

    monkeypatch.setattr(lifecycle.usage_service.usage_storage, "append", fail_after_token_record)
    assert workers.run_one_job(queue=queue)
    job = queue.for_workflow(workflow_id)
    assert job.status == "retrying"
    assert lifecycle.get_workflow(workflow_id).telemetry.token_usage.total_tokens == 15
    with queue.connect(write=True) as conn:
        conn.execute("UPDATE analytics_jobs SET available_at = 0 WHERE job_id = ?", (job.job_id,))
    assert workers.run_one_job(queue=queue)
    records = lifecycle.usage_service.list_usage(workspace_id="default-team.admin")
    tokens = [item for item in records if item.event_type == "token_usage"]
    costs = [item for item in records if item.event_type == "estimated_ai_cost"]
    assert len(tokens) == 1 and tokens[0].quantity == 15
    assert len(costs) == 1 and costs[0].estimated_cost_usd == 0.001


def test_simulator_holds_activity_guard_until_background_run_finishes(analytics_client, monkeypatch):
    import asyncio
    from backend.runtime import OrchestrationRuntime
    from backend.workers import ActiveJobsError
    _, queue, _, _, _, lifecycle = analytics_client
    scope = ("organization:default-team", "default-team.admin")
    workflow = lifecycle.create_workflow("Synthetic lifecycle", organization_id=scope[0], workspace_id=scope[1])
    complete = lifecycle.complete_stage
    protected_stages = []

    def complete_while_deletion_attempts(workflow_id, stage):
        with pytest.raises(ActiveJobsError):
            with queue.workspace_deletion(*scope):
                pytest.fail("A running simulator must exclude workspace deletion")
        protected_stages.append(stage)
        return complete(workflow_id, stage)

    monkeypatch.setattr(lifecycle, "complete_stage", complete_while_deletion_attempts)
    result = asyncio.run(OrchestrationRuntime(service=lifecycle).run(workflow.workflow_id))
    assert result.status == "completed"
    assert len(protected_stages) == 6
    with queue.workspace_deletion(*scope):
        pass
