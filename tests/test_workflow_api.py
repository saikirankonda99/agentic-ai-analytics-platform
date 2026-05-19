from __future__ import annotations

from fastapi.testclient import TestClient

from backend.main import app


def test_execute_and_fetch_workflow() -> None:
    client = TestClient(app)

    created = client.post("/execute", json={"question": "Show revenue anomalies"}).json()
    workflow_id = created["workflow_id"]
    fetched = client.get(f"/workflow/{workflow_id}").json()
    events = client.get(f"/workflow/{workflow_id}/events").json()
    telemetry = client.get(f"/workflow/{workflow_id}/telemetry").json()
    replay = client.get(f"/workflow/{workflow_id}/replay").json()
    telemetry_events = client.get(f"/workflow/{workflow_id}/telemetry/events").json()
    execution_graph = client.get(f"/workflow/{workflow_id}/execution-graph").json()
    telemetry_aggregate = client.get(f"/workflow/{workflow_id}/telemetry/aggregate").json()

    assert created["status"] == "queued"
    assert fetched["status"] == "completed"
    assert fetched["telemetry"]["latency_ms"] is not None
    assert len(fetched["agent_executions"]) >= 6
    assert events["workflow_id"] == workflow_id
    assert telemetry["token_usage"]["total_tokens"] >= 0
    assert replay["workflow_id"] == workflow_id
    assert replay["updates"]
    assert telemetry_events["workflow_id"] == workflow_id
    assert execution_graph["summary"]["node_count"] >= 6
    assert execution_graph["replay"]["frame_count"] == len(replay["updates"])
    assert telemetry_aggregate["aggregate"]["event_count"] >= 1


def test_health_and_readiness() -> None:
    client = TestClient(app)

    assert client.get("/health").json()["status"] == "ok"
    readiness = client.get("/ready").json()
    diagnostics = client.get("/diagnostics").json()

    assert readiness["status"] in {"ready", "degraded"}
    assert readiness["workflow_storage"] == "ok"
    assert diagnostics["telemetry_schema_version"]
    assert "openai" in diagnostics
    assert "execution_policy" in diagnostics
    assert client.get("/telemetry/schema").json()["schema_version"]
    assert client.get("/operations/summary").json()["telemetry_schema_version"]
    assert client.get("/investigations/latest").json()["status"] in {"empty", "idle", "running", "completed", "failed"}


def test_workspace_inspection_api() -> None:
    client = TestClient(app)

    inspection = client.get("/workspace/default-team.local.user/inspection").json()
    transcripts = client.get("/workspace/default-team.local.user/transcripts").json()
    sql_history = client.get("/workspace/default-team.local.user/sql-history").json()

    assert inspection["workspace_id"] == "default-team.local.user"
    assert "telemetry" in inspection
    assert transcripts["workspace_id"] == "default-team.local.user"
    assert "items" in sql_history
