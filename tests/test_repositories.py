from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from backend.models import OrchestrationExecution, WorkflowEvent, WorkflowTelemetry
from backend.storage import SQLiteEventStorage, SQLiteTelemetryStorage, SQLiteWorkflowStorage


def test_sqlite_workflow_event_and_telemetry_repositories() -> None:
    runtime_dir = Path("data") / "test-runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    db_path = runtime_dir / f"{uuid4()}.db"
    workflow_storage = SQLiteWorkflowStorage(db_path)
    event_storage = SQLiteEventStorage(db_path)
    telemetry_storage = SQLiteTelemetryStorage(db_path)

    workflow = OrchestrationExecution(
        workflow_id="workflow:test",
        workspace_id="workspace:test",
        question="What changed?",
        status="queued",
        created_at="2026-05-18T00:00:00+00:00",
        telemetry=WorkflowTelemetry(),
    )

    workflow_storage.save(workflow)
    event_storage.append(
        workflow.workflow_id,
        WorkflowEvent(
            timestamp=workflow.created_at,
            event_type="workflow_created",
            message="created",
        ),
        workspace_id=workflow.workspace_id,
    )
    telemetry_storage.save(workflow.workflow_id, workflow.telemetry, workspace_id=workflow.workspace_id)

    assert workflow_storage.get(workflow.workflow_id).workspace_id == "workspace:test"
    assert event_storage.list(workflow.workflow_id, workspace_id=workflow.workspace_id)[0].message == "created"
    assert telemetry_storage.get(workflow.workflow_id).estimated_cost_usd == 0.0
