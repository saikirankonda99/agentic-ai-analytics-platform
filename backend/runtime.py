from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Protocol

from backend.models import (
    DEFAULT_ORGANIZATION_ID,
    DEFAULT_USER_ID,
    DEFAULT_WORKSPACE_ID,
    WORKFLOW_STAGES,
    OrchestrationExecution,
    WorkflowStreamUpdate,
)
from backend.logging import get_logger
from backend.services import OrchestrationService, orchestration_service
from backend.websocket import WebSocketConnectionManager, websocket_manager, workflow_channel

logger = get_logger(__name__)


class RuntimeScheduler(Protocol):
    def add_task(self, func: Callable[[str], Awaitable[OrchestrationExecution]], workflow_id: str) -> None:
        """Schedule workflow execution outside the request/response path."""


@dataclass
class OrchestrationRuntime:
    service: OrchestrationService
    websocket_connections: WebSocketConnectionManager = websocket_manager
    _published_updates: set[tuple[str, str, str, str]] = field(default_factory=set)

    def submit(
        self,
        question: str,
        scheduler: RuntimeScheduler,
        workspace_id: str = DEFAULT_WORKSPACE_ID,
        organization_id: str = DEFAULT_ORGANIZATION_ID,
        user_id: str = DEFAULT_USER_ID,
    ) -> OrchestrationExecution:
        workflow = self.service.create_workflow(
            question,
            workspace_id=workspace_id,
            organization_id=organization_id,
            user_id=user_id,
        )
        scheduler.add_task(self.run, workflow.workflow_id)
        logger.info("workflow_submitted workflow_id=%s workspace_id=%s", workflow.workflow_id, workspace_id)
        return workflow

    async def run(self, workflow_id: str) -> OrchestrationExecution:
        try:
            logger.info("workflow_run_started workflow_id=%s", workflow_id)
            workflow = self.service.start_workflow(workflow_id)
            await self._broadcast_new(workflow, {"workflow_event", "lifecycle_transition", "telemetry_update"})
            for stage in WORKFLOW_STAGES:
                workflow = self.service.complete_stage(workflow_id, stage)
                await self._broadcast_new(
                    workflow,
                    {"workflow_event", "stage_transition", "agent_update", "investigation_update"},
                )
            workflow = self.service.complete_workflow(workflow_id)
            await self._broadcast_new(workflow, {"workflow_event", "lifecycle_transition", "telemetry_update"})
            await self._broadcast_investigation_placeholder(workflow)
            logger.info("workflow_run_completed workflow_id=%s", workflow_id)
            return workflow
        except Exception:
            logger.exception("workflow_run_failed workflow_id=%s", workflow_id)
            try:
                workflow = self.service.fail_workflow(workflow_id)
                await self._broadcast_new(workflow, {"workflow_event", "lifecycle_transition", "telemetry_update"})
                return workflow
            except Exception:
                logger.exception("workflow_failure_state_update_failed workflow_id=%s", workflow_id)
                raise

    async def _broadcast_new(
        self,
        workflow: OrchestrationExecution,
        update_types: set[str],
    ) -> None:
        updates = [
            update
            for update in (self.service.get_stream_updates(workflow.workflow_id) or ())
            if update.update_type in update_types
        ]
        for update in updates:
            update_key = (workflow.workflow_id, update.timestamp, update.update_type, update.message)
            if update_key in self._published_updates:
                continue
            self._published_updates.add(update_key)
            await self.websocket_connections.broadcast(
                workflow_channel(workflow.workflow_id, workflow.workspace_id, workflow.organization_id),
                update,
            )

    async def _broadcast_investigation_placeholder(self, workflow: OrchestrationExecution) -> None:
        update = WorkflowStreamUpdate(
            timestamp=workflow.telemetry.completed_at or workflow.created_at,
            update_type="investigation_update",
            message="Autonomous investigation updates are ready for future runtime integration.",
            payload={
                "workflow_id": workflow.workflow_id,
                "organization_id": workflow.organization_id,
                "workspace_id": workflow.workspace_id,
                "status": "not_started",
            },
        )
        await self.websocket_connections.broadcast(
            workflow_channel(workflow.workflow_id, workflow.workspace_id, workflow.organization_id),
            update,
        )


orchestration_runtime = OrchestrationRuntime(service=orchestration_service)


__all__ = ["OrchestrationRuntime", "RuntimeScheduler", "orchestration_runtime"]
