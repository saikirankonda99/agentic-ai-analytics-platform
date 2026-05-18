from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Callable, Literal
from uuid import uuid4

from backend.ports import BackendConfig, InMemoryCache, InlineWorker


if TYPE_CHECKING:
    from graph.workflow import WorkflowState


WorkflowCallback = Callable[[str, "WorkflowState", str, str], None]
WorkflowLifecycleState = Literal["queued", "running", "completed", "failed"]


@dataclass(frozen=True)
class OrchestrationExecution:
    workflow_id: str
    question: str
    status: WorkflowLifecycleState
    created_at: str


class OrchestrationService:
    def __init__(self, config: BackendConfig | None = None) -> None:
        self.config = config or BackendConfig()
        self.cache = InMemoryCache()
        self.worker = InlineWorker()

    def execute(self, question: str) -> OrchestrationExecution:
        execution = OrchestrationExecution(
            workflow_id=f"workflow:{uuid4()}",
            question=question,
            status="queued",
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self._save_workflow(execution)

        try:
            self._transition_workflow(execution.workflow_id, "running")
            return self._transition_workflow(execution.workflow_id, "completed")
        except Exception:
            return self._transition_workflow(execution.workflow_id, "failed")

    def get_workflow(self, workflow_id: str) -> OrchestrationExecution | None:
        workflow = self.cache.get(workflow_id)
        if isinstance(workflow, OrchestrationExecution):
            return workflow
        return None

    def _save_workflow(self, workflow: OrchestrationExecution) -> None:
        self.cache.set(workflow.workflow_id, workflow)
        self.cache.set("workflow:latest", workflow)

    def _transition_workflow(
        self,
        workflow_id: str,
        status: WorkflowLifecycleState,
    ) -> OrchestrationExecution:
        workflow = self.get_workflow(workflow_id)
        if workflow is None:
            raise ValueError(f"Workflow not found: {workflow_id}")

        updated = OrchestrationExecution(
            workflow_id=workflow.workflow_id,
            question=workflow.question,
            status=status,
            created_at=workflow.created_at,
        )
        self._save_workflow(updated)
        return updated


class AnalyticsBackendService:
    def __init__(self, config: BackendConfig | None = None) -> None:
        self.config = config or BackendConfig()
        self.cache = InMemoryCache()
        self.worker = InlineWorker()

    def execute_query(
        self,
        question: str,
        *,
        semantic_context: dict[str, Any] | None = None,
        conversation_context: dict[str, Any] | None = None,
        workspace_context: dict[str, Any] | None = None,
        callback: WorkflowCallback | None = None,
    ) -> dict[str, Any]:
        from db import get_schema
        from graph.workflow import run_workflow
        from semantic import profile_schema, semantic_prompt_block

        schema_context = semantic_context or profile_schema(get_schema(), name="Chinook SQL schema")
        workflow_context = {**schema_context, "prompt_block": semantic_prompt_block(schema_context)}
        result = run_workflow(
            question,
            callback=callback,
            semantic_context=workflow_context,
            conversation_context=conversation_context,
            workspace_context=workspace_context,
        )
        run_id = f"workflow:{datetime.now().isoformat(timespec='seconds')}"
        self.cache.set(run_id, result)
        self.cache.set("workflow:latest", result)
        return dict(result)

    def workflow_status(self, run_id: str = "workflow:latest") -> dict[str, Any]:
        return self.cache.get(run_id) or {}

    def telemetry(self, run_id: str = "workflow:latest") -> dict[str, Any]:
        return (self.workflow_status(run_id) or {}).get("telemetry", {})

    def profile_result(self, columns: list[str], rows: list[Any], name: str) -> dict[str, Any]:
        import pandas as pd
        from semantic import profile_dataframe

        return profile_dataframe(pd.DataFrame(rows, columns=columns), name=name)

    def run_investigation(
        self,
        *,
        question: str,
        sql: str,
        insight_state: dict[str, Any],
        semantic_context: dict[str, Any] | None = None,
        max_queries: int = 3,
    ) -> dict[str, Any]:
        from investigation import run_investigation

        result = run_investigation(question, sql, insight_state, semantic_context, max_queries=max_queries)
        self.cache.set("investigation:latest", result)
        return result

    def executive_briefing(
        self,
        *,
        targets: list[str],
        semantic_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        from monitoring import run_monitoring_checks

        monitoring_state, briefing = run_monitoring_checks(targets, semantic_context)
        self.cache.set("monitoring:latest", monitoring_state)
        self.cache.set("briefing:latest", briefing)
        return {"monitoring": monitoring_state, "briefing": briefing}

    def briefing_from_monitoring(self, monitoring_state: dict[str, Any]) -> dict[str, Any]:
        from monitoring import generate_executive_briefing

        briefing = generate_executive_briefing(monitoring_state)
        self.cache.set("briefing:latest", briefing)
        return briefing

    def analyze_result(self, columns: list[str], rows: list[Any], question: str) -> dict[str, Any]:
        import pandas as pd
        from autonomous_insights import analyze_result_set

        result = analyze_result_set(pd.DataFrame(rows, columns=columns), question)
        self.cache.set("insight:latest", result)
        return result

    def execute_sql(self, sql: str) -> dict[str, Any]:
        from db import run_query

        columns, rows = run_query(sql)
        return {"columns": columns, "rows": rows, "count": len(rows)}


backend_service = AnalyticsBackendService()
orchestration_service = OrchestrationService()


def execute_query_workflow(
    question: str,
    *,
    semantic_context: dict[str, Any] | None = None,
    conversation_context: dict[str, Any] | None = None,
    workspace_context: dict[str, Any] | None = None,
    callback: WorkflowCallback | None = None,
) -> dict[str, Any]:
    return backend_service.execute_query(
        question,
        semantic_context=semantic_context,
        conversation_context=conversation_context,
        workspace_context=workspace_context,
        callback=callback,
    )
