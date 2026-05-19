from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from backend.governance import default_dataset_registry, default_workspace_policy, governance_overview, validate_dataset_access
from backend.incidents import incident_from_telemetry
from backend.main import app
from backend.scheduler import next_run_at, scheduler_overview


def test_governance_overview_scores_datasets_and_policy_access() -> None:
    overview = governance_overview("workspace:test")
    dataset = default_dataset_registry()[0]
    access = validate_dataset_access(dataset, default_workspace_policy("workspace:test"))

    assert overview["summary"]["dataset_count"] >= 3
    assert overview["summary"]["average_trust_score"] > 0
    assert access["allowed"] is True
    assert overview["audit_metadata"]["retention"]["telemetry_days"] == 30


def test_scheduler_overview_supports_recurring_windows() -> None:
    now = datetime(2026, 5, 19, 7, 30, tzinfo=timezone.utc)
    overview = scheduler_overview("workspace:test")

    assert next_run_at("hourly", now).endswith("08:00:00+00:00")
    assert next_run_at("daily@08:00", now).endswith("08:00:00+00:00")
    assert overview["active_count"] >= 1
    assert overview["observability"]["scheduler_health"] == "healthy"


def test_incident_generation_scores_runtime_degradation() -> None:
    incident = incident_from_telemetry(
        {
            "correlation_id": "wf-test",
            "failure_rate": 30,
            "latency_ms": 16000,
            "cost_usd": 0.2,
        },
        workflow_id="workflow:test",
    )

    assert incident is not None
    assert incident.severity == "critical"
    assert incident.escalation["requires_executive_visibility"] is True


def test_enterprise_control_plane_endpoints() -> None:
    client = TestClient(app)
    created = client.post("/execute", json={"question": "Show revenue anomalies"}).json()
    workflow_id = created["workflow_id"]

    governance = client.get("/governance").json()
    scheduler = client.get("/scheduler").json()
    incidents = client.get(f"/incidents?workflow_id={workflow_id}").json()
    report = client.get(f"/executive/report?workflow_id={workflow_id}").json()
    timeline = client.get(f"/audit/timeline?workflow_id={workflow_id}").json()

    assert governance["summary"]["dataset_count"] >= 3
    assert scheduler["schedule_count"] >= 3
    assert "incident_count" in incidents
    assert report["report_type"] == "ai_data_operations"
    assert report["scorecard"]["readiness_score"] >= 0
    assert timeline["timeline"]
