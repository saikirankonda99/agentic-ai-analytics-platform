from __future__ import annotations

from fastapi.testclient import TestClient

from backend.main import app


def test_execute_and_fetch_workflow() -> None:
    client = TestClient(app)

    created = client.post("/execute", json={"question": "Show revenue anomalies"}).json()
    workflow_id = created["workflow_id"]
    fetched = client.get(f"/workflow/{workflow_id}").json()
    events = client.get(f"/workflow/{workflow_id}/events").json()

    assert created["status"] == "queued"
    assert fetched["status"] == "completed"
    assert fetched["telemetry"]["latency_ms"] is not None
    assert len(fetched["agent_executions"]) >= 6
    assert events["workflow_id"] == workflow_id


def test_health_and_readiness() -> None:
    client = TestClient(app)

    assert client.get("/health").json()["status"] == "ok"
    readiness = client.get("/ready").json()

    assert readiness["status"] in {"ready", "degraded"}
    assert readiness["workflow_storage"] == "ok"
