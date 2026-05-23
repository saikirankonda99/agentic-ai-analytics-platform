from __future__ import annotations

import gc
import time
from pathlib import Path
from uuid import uuid4

from backend.models import (
    OrchestrationExecution,
    UsageRecord,
    WorkflowEvent,
    WorkflowStageProgress,
    WorkflowTelemetry,
)
from backend.config import AppSettings
from backend.storage import (
    SQLiteEventStorage,
    SQLiteTelemetryStorage,
    SQLiteUsageStorage,
    SQLiteWorkflowStorage,
    _stage_progression_from_payload,
    _usage_from_row,
    build_workflow_storage,
    use_postgresql_storage,
    validate_workflow_storage,
)


def _remove_sqlite_file(db_path: Path) -> None:
    gc.collect()
    for path in (db_path, db_path.with_suffix(".db-shm"), db_path.with_suffix(".db-wal")):
        for _ in range(3):
            try:
                path.unlink(missing_ok=True)
                break
            except PermissionError:
                time.sleep(0.05)


def test_sqlite_workflow_event_and_telemetry_repositories() -> None:
    runtime_root = Path("data") / "test-runtime"
    runtime_root.mkdir(parents=True, exist_ok=True)
    db_path = runtime_root / f"repository-{uuid4().hex}.db"
    try:
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
    finally:
        _remove_sqlite_file(db_path)


def test_sqlite_storage_serialization_and_transaction_rollback() -> None:
    runtime_root = Path("data") / "test-runtime"
    runtime_root.mkdir(parents=True, exist_ok=True)
    db_path = runtime_root / f"repository-{uuid4().hex}.db"
    try:
        workflow_storage = SQLiteWorkflowStorage(db_path)
        usage_storage = SQLiteUsageStorage(db_path)
        workflow = OrchestrationExecution(
            workflow_id="workflow:serialized",
            workspace_id="workspace:test",
            question="What serialized?",
            status="running",
            created_at="2026-05-18T00:00:00+00:00",
            stage_progression=(
                WorkflowStageProgress(stage="planning", status="completed", timestamp="2026-05-18T00:00:01+00:00"),
            ),
            telemetry=WorkflowTelemetry(),
        )

        workflow_storage.save(workflow)
        usage_storage.append(
            UsageRecord(
                usage_id="usage:test",
                organization_id="organization:test",
                workspace_id="workspace:test",
                user_id="user:test",
                event_type="workflow_execution",
                quantity=1,
                estimated_cost_usd=0.25,
                timestamp="2026-05-18T00:00:02+00:00",
                metadata={"nested": {"ok": True}},
            )
        )

        try:
            with workflow_storage._transaction("test.rollback") as connection:
                connection.execute(
                    "INSERT INTO workflows (workflow_id, question, status, created_at) VALUES (?, ?, ?, ?)",
                    ("workflow:rollback", "rollback", "queued", "2026-05-18T00:00:03+00:00"),
                )
                raise RuntimeError("force rollback")
        except RuntimeError:
            pass

        restored = workflow_storage.get("workflow:serialized")
        usage = usage_storage.list(workspace_id="workspace:test")[0]

        assert restored.stage_progression[0].stage == "planning"
        assert usage.metadata["nested"]["ok"] is True
        assert workflow_storage.get("workflow:rollback") is None
    finally:
        _remove_sqlite_file(db_path)


def test_workflow_storage_factory_uses_workflow_database_url(monkeypatch) -> None:
    import backend.storage as storage

    runtime_root = Path("data") / "test-runtime"
    runtime_root.mkdir(parents=True, exist_ok=True)
    db_path = runtime_root / f"workflow-factory-{uuid4().hex}.db"
    try:
        monkeypatch.setattr(
            storage,
            "settings",
            AppSettings(
                database_url="postgresql://platform:secret@localhost:5432/platform",
                workflow_database_url=f"sqlite:///{db_path}",
                workflow_database_source="WORKFLOW_DATABASE_URL",
            ),
        )

        workflow_storage = build_workflow_storage()

        assert isinstance(workflow_storage, SQLiteWorkflowStorage)
        assert workflow_storage.db_path == db_path
        assert use_postgresql_storage() is False
    finally:
        _remove_sqlite_file(db_path)


def test_workflow_storage_validation_reports_selected_backend() -> None:
    runtime_root = Path("data") / "test-runtime"
    runtime_root.mkdir(parents=True, exist_ok=True)
    db_path = runtime_root / f"workflow-validation-{uuid4().hex}.db"
    try:
        diagnostics = validate_workflow_storage(f"sqlite:///{db_path}")

        assert diagnostics["status"] == "ok"
        assert diagnostics["backend"] == "sqlite"
        assert diagnostics["database_url"] == f"sqlite:///{db_path}"
    finally:
        _remove_sqlite_file(db_path)


def test_postgresql_jsonb_native_stage_progression_deserializes() -> None:
    stages = _stage_progression_from_payload(
        [
            {
                "stage": "planning",
                "status": "completed",
                "timestamp": "2026-05-18T00:00:01+00:00",
                "latency_ms": 12,
                "error": None,
            }
        ]
    )

    assert len(stages) == 1
    assert stages[0].stage == "planning"
    assert stages[0].status == "completed"


def test_postgresql_jsonb_native_usage_metadata_deserializes() -> None:
    usage = _usage_from_row(
        {
            "usage_id": "usage:jsonb",
            "organization_id": "organization:test",
            "workspace_id": "workspace:test",
            "user_id": "user:test",
            "event_type": "workflow_execution",
            "quantity": 1.0,
            "estimated_cost_usd": 0.25,
            "timestamp": "2026-05-18T00:00:02+00:00",
            "metadata_json": {"nested": {"ok": True}, "source": "postgres-jsonb"},
        }
    )

    assert usage.metadata["nested"]["ok"] is True
    assert usage.metadata["source"] == "postgres-jsonb"


def test_storage_json_deserialization_falls_back_for_legacy_corrupt_payloads() -> None:
    stages = _stage_progression_from_payload("{not-json")
    usage = _usage_from_row(
        {
            "usage_id": "usage:legacy-corrupt",
            "organization_id": "organization:test",
            "workspace_id": "workspace:test",
            "user_id": "user:test",
            "event_type": "workflow_execution",
            "quantity": 1.0,
            "estimated_cost_usd": 0.25,
            "timestamp": "2026-05-18T00:00:02+00:00",
            "metadata_json": ["not", "an", "object"],
        }
    )

    assert stages == ()
    assert usage.metadata == {}
