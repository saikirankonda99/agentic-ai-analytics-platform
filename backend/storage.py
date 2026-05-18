from __future__ import annotations

from typing import TYPE_CHECKING, Protocol


if TYPE_CHECKING:
    from backend.services import OrchestrationExecution, WorkflowEvent, WorkflowTelemetry


class WorkflowStorage(Protocol):
    def save(self, workflow: OrchestrationExecution) -> None:
        """Persist workflow state."""

    def get(self, workflow_id: str) -> OrchestrationExecution | None:
        """Load workflow state by id."""


class EventStorage(Protocol):
    def append(self, workflow_id: str, event: WorkflowEvent) -> None:
        """Append an event to a workflow event stream."""

    def list(self, workflow_id: str) -> tuple[WorkflowEvent, ...]:
        """List events for a workflow."""


class TelemetryStorage(Protocol):
    def save(self, workflow_id: str, telemetry: WorkflowTelemetry) -> None:
        """Persist workflow telemetry."""

    def get(self, workflow_id: str) -> WorkflowTelemetry | None:
        """Load workflow telemetry by workflow id."""


class InMemoryWorkflowStorage:
    def __init__(self) -> None:
        self._workflows: dict[str, OrchestrationExecution] = {}
        self._latest_workflow_id: str | None = None

    def save(self, workflow: OrchestrationExecution) -> None:
        self._workflows[workflow.workflow_id] = workflow
        self._latest_workflow_id = workflow.workflow_id

    def get(self, workflow_id: str) -> OrchestrationExecution | None:
        if workflow_id == "workflow:latest" and self._latest_workflow_id is not None:
            return self._workflows.get(self._latest_workflow_id)
        return self._workflows.get(workflow_id)


class InMemoryEventStorage:
    def __init__(self) -> None:
        self._events: dict[str, tuple[WorkflowEvent, ...]] = {}

    def append(self, workflow_id: str, event: WorkflowEvent) -> None:
        self._events[workflow_id] = (*self._events.get(workflow_id, ()), event)

    def list(self, workflow_id: str) -> tuple[WorkflowEvent, ...]:
        return self._events.get(workflow_id, ())


class InMemoryTelemetryStorage:
    def __init__(self) -> None:
        self._telemetry: dict[str, WorkflowTelemetry] = {}

    def save(self, workflow_id: str, telemetry: WorkflowTelemetry) -> None:
        self._telemetry[workflow_id] = telemetry

    def get(self, workflow_id: str) -> WorkflowTelemetry | None:
        return self._telemetry.get(workflow_id)


__all__ = [
    "EventStorage",
    "InMemoryEventStorage",
    "InMemoryTelemetryStorage",
    "InMemoryWorkflowStorage",
    "TelemetryStorage",
    "WorkflowStorage",
]
