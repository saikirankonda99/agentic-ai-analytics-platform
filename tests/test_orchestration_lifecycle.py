from __future__ import annotations

from backend.services import OrchestrationService
from backend.storage import (
    InMemoryAgentExecutionStorage,
    InMemoryAgentTraceStorage,
    InMemoryEventStorage,
    InMemoryTelemetryStorage,
    InMemoryWorkflowStorage,
)


def test_lifecycle_generates_telemetry_and_agent_traces() -> None:
    service = OrchestrationService(
        workflow_storage=InMemoryWorkflowStorage(),
        event_storage=InMemoryEventStorage(),
        telemetry_storage=InMemoryTelemetryStorage(),
        agent_execution_storage=InMemoryAgentExecutionStorage(),
        agent_trace_storage=InMemoryAgentTraceStorage(),
    )

    created = service.create_workflow("Find revenue anomalies", workspace_id="workspace:test")
    completed = service.run_workflow(created.workflow_id)
    events = service.get_events(created.workflow_id) or ()
    traces = service.get_agent_traces(created.workflow_id) or ()

    assert completed.status == "completed"
    assert completed.current_stage == "insight_generation"
    assert completed.telemetry.completed_at is not None
    assert completed.telemetry.token_usage.total_tokens > 0
    assert len(completed.agent_executions) >= 10
    assert any(event.event_type == "investigation_update" for event in events)
    assert traces
