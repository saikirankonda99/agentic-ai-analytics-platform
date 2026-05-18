from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from backend.services import WORKFLOW_STAGES, OrchestrationExecution, OrchestrationService, orchestration_service


class RuntimeScheduler(Protocol):
    def add_task(self, func: Callable[[str], OrchestrationExecution], workflow_id: str) -> None:
        """Schedule workflow execution outside the request/response path."""


@dataclass
class OrchestrationRuntime:
    service: OrchestrationService

    def submit(self, question: str, scheduler: RuntimeScheduler) -> OrchestrationExecution:
        workflow = self.service.create_workflow(question)
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
