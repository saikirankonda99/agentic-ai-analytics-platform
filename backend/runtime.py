from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from backend.models import DEFAULT_WORKSPACE_ID, WORKFLOW_STAGES, OrchestrationExecution
from backend.services import OrchestrationService, orchestration_service


class RuntimeScheduler(Protocol):
    def add_task(self, func: Callable[[str], OrchestrationExecution], workflow_id: str) -> None:
        """Schedule workflow execution outside the request/response path."""


@dataclass
class OrchestrationRuntime:
    service: OrchestrationService

    def submit(
        self,
        question: str,
        scheduler: RuntimeScheduler,
        workspace_id: str = DEFAULT_WORKSPACE_ID,
    ) -> OrchestrationExecution:
        workflow = self.service.create_workflow(question, workspace_id=workspace_id)
        scheduler.add_task(self.run, workflow.workflow_id)
        return workflow

    def run(self, workflow_id: str) -> OrchestrationExecution:
        try:
            self.service.start_workflow(workflow_id)
            for stage in WORKFLOW_STAGES:
                self.service.complete_stage(workflow_id, stage)
            return self.service.complete_workflow(workflow_id)
        except Exception:
            return self.service.fail_workflow(workflow_id)


orchestration_runtime = OrchestrationRuntime(service=orchestration_service)


__all__ = ["OrchestrationRuntime", "RuntimeScheduler", "orchestration_runtime"]
