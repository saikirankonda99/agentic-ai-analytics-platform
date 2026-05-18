from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Callable, Literal
from uuid import uuid4

from backend.ports import BackendConfig, InMemoryCache, InlineWorker


if TYPE_CHECKING:
    from graph.workflow import WorkflowState


WorkflowCallback = Callable[[str, "WorkflowState", str, str], None]
WorkflowLifecycleState = Literal["queued", "running", "completed", "failed"]
AgentExecutionStatus = Literal["queued", "running", "completed", "failed"]
WorkflowStage = Literal[
    "planning",
    "schema_analysis",
    "sql_generation",
    "validation",
    "execution",
    "insight_generation",
]
WorkflowEventType = Literal[
    "workflow_created",
    "lifecycle_transition",
    "stage_transition",
    "telemetry_update",
]
WORKFLOW_STAGES: tuple[WorkflowStage, ...] = (
    "planning",
    "schema_analysis",
    "sql_generation",
    "validation",
    "execution",
    "insight_generation",
)
STAGE_AGENTS: dict[WorkflowStage, tuple[str, str]] = {
    "planning": ("planner_agent", "Workflow planner"),
    "schema_analysis": ("schema_agent", "Schema analyst"),
    "sql_generation": ("sql_agent", "SQL generator"),
    "validation": ("validation_agent", "Query validator"),
    "execution": ("execution_agent", "Query executor"),
    "insight_generation": ("insight_agent", "Insight generator"),
}


@dataclass(frozen=True)
class TokenUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass(frozen=True)
class WorkflowTelemetry:
    started_at: str | None = None
    completed_at: str | None = None
    latency_ms: int | None = None
    estimated_cost_usd: float = 0.0
    token_usage: TokenUsage = field(default_factory=TokenUsage)


@dataclass(frozen=True)
class WorkflowStageProgress:
    stage: WorkflowStage
    status: WorkflowLifecycleState
    timestamp: str


@dataclass(frozen=True)
class AgentExecution:
    agent_name: str
    agent_role: str
    assigned_stage: WorkflowStage
    agent_status: AgentExecutionStatus


@dataclass(frozen=True)
class WorkflowEvent:
    timestamp: str
    event_type: WorkflowEventType
    message: str


@dataclass(frozen=True)
class OrchestrationExecution:
    workflow_id: str
    question: str
    status: WorkflowLifecycleState
    created_at: str
    telemetry: WorkflowTelemetry
    current_stage: WorkflowStage | None = None
    stage_progression: tuple[WorkflowStageProgress, ...] = ()
    agent_executions: tuple[AgentExecution, ...] = ()


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
            telemetry=WorkflowTelemetry(),
        )
        self._save_workflow(execution)
        self._append_event(
            execution.workflow_id,
            "workflow_created",
            f"Workflow created for question: {question}",
        )

        try:
            self._transition_workflow(execution.workflow_id, "running")
            for stage in WORKFLOW_STAGES:
                self._transition_stage(execution.workflow_id, stage)
            return self._transition_workflow(execution.workflow_id, "completed")
        except Exception:
            return self._transition_workflow(execution.workflow_id, "failed")

    def get_workflow(self, workflow_id: str) -> OrchestrationExecution | None:
        workflow = self.cache.get(workflow_id)
        if isinstance(workflow, OrchestrationExecution):
            return workflow
        return None

    def get_events(self, workflow_id: str) -> tuple[WorkflowEvent, ...] | None:
        if self.get_workflow(workflow_id) is None:
            return None

        events = self.cache.get(self._events_key(workflow_id))
        if isinstance(events, tuple):
            return events
        return ()

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
            telemetry=self._build_telemetry(workflow, status),
            current_stage=workflow.current_stage,
            stage_progression=workflow.stage_progression,
            agent_executions=workflow.agent_executions,
        )
        self._save_workflow(updated)
        self._append_event(
            workflow_id,
            "lifecycle_transition",
            f"Workflow status changed to {status}.",
        )
        if updated.telemetry != workflow.telemetry:
            self._append_event(
                workflow_id,
                "telemetry_update",
                f"Workflow telemetry updated for {status} status.",
            )
        return updated

    def _transition_stage(
        self,
        workflow_id: str,
        stage: WorkflowStage,
    ) -> OrchestrationExecution:
        workflow = self.get_workflow(workflow_id)
        if workflow is None:
            raise ValueError(f"Workflow not found: {workflow_id}")

        updated = OrchestrationExecution(
            workflow_id=workflow.workflow_id,
            question=workflow.question,
            status=workflow.status,
            created_at=workflow.created_at,
            telemetry=workflow.telemetry,
            current_stage=stage,
            stage_progression=(
                *workflow.stage_progression,
                WorkflowStageProgress(
                    stage=stage,
                    status="completed",
                    timestamp=datetime.now(timezone.utc).isoformat(),
                ),
            ),
            agent_executions=(
                *workflow.agent_executions,
                self._simulate_agent_execution(stage),
            ),
        )
        self._save_workflow(updated)
        self._append_event(
            workflow_id,
            "stage_transition",
            f"Workflow stage completed: {stage}.",
        )
        return updated

    def _append_event(
        self,
        workflow_id: str,
        event_type: WorkflowEventType,
        message: str,
    ) -> None:
        event = WorkflowEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            event_type=event_type,
            message=message,
        )
        events = self.cache.get(self._events_key(workflow_id))
        if not isinstance(events, tuple):
            events = ()
        self.cache.set(self._events_key(workflow_id), (*events, event))

    def _events_key(self, workflow_id: str) -> str:
        return f"{workflow_id}:events"

    def _simulate_agent_execution(self, stage: WorkflowStage) -> AgentExecution:
        agent_name, agent_role = STAGE_AGENTS[stage]
        return AgentExecution(
            agent_name=agent_name,
            agent_role=agent_role,
            assigned_stage=stage,
            agent_status="completed",
        )

    def _build_telemetry(
        self,
        workflow: OrchestrationExecution,
        status: WorkflowLifecycleState,
    ) -> WorkflowTelemetry:
        if status == "running":
            return WorkflowTelemetry(started_at=datetime.now(timezone.utc).isoformat())

        if status not in {"completed", "failed"}:
            return workflow.telemetry

        completed_at = datetime.now(timezone.utc)
        started_at = workflow.telemetry.started_at or completed_at.isoformat()
        started_at_dt = datetime.fromisoformat(started_at)
        latency_ms = max(int((completed_at - started_at_dt).total_seconds() * 1000), 0)
        token_usage = self._estimate_token_usage(workflow.question)

        return WorkflowTelemetry(
            started_at=started_at,
            completed_at=completed_at.isoformat(),
            latency_ms=latency_ms,
            estimated_cost_usd=self._estimate_cost(token_usage),
            token_usage=token_usage,
        )

    def _estimate_token_usage(self, question: str) -> TokenUsage:
        prompt_tokens = max(len(question.split()), 1) + 16
        completion_tokens = 24
        return TokenUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        )

    def _estimate_cost(self, token_usage: TokenUsage) -> float:
        return round(token_usage.total_tokens * 0.000002, 6)


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
