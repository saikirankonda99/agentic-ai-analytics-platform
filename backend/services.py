from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Callable
from uuid import uuid4

from backend.memory import InMemoryVectorMemoryStore, VectorMemoryStore
from backend.models import (
    STAGE_AGENTS,
    WORKFLOW_STAGES,
    AgentExecution,
    OrchestrationExecution,
    TokenUsage,
    WorkflowEvent,
    WorkflowEventType,
    WorkflowLifecycleState,
    WorkflowStage,
    WorkflowStageProgress,
    WorkflowStreamUpdate,
    WorkflowTelemetry,
)
from backend.ports import BackendConfig, InMemoryCache, InlineWorker
from backend.storage import (
    AgentExecutionStorage,
    EventStorage,
    SQLiteAgentExecutionStorage,
    SQLiteEventStorage,
    SQLiteTelemetryStorage,
    SQLiteWorkflowStorage,
    TelemetryStorage,
    WorkflowStorage,
)


if TYPE_CHECKING:
    from graph.workflow import WorkflowState


WorkflowCallback = Callable[[str, "WorkflowState", str, str], None]


class OrchestrationService:
    def __init__(
        self,
        config: BackendConfig | None = None,
        workflow_storage: WorkflowStorage | None = None,
        event_storage: EventStorage | None = None,
        telemetry_storage: TelemetryStorage | None = None,
        agent_execution_storage: AgentExecutionStorage | None = None,
        vector_memory_store: VectorMemoryStore | None = None,
    ) -> None:
        self.config = config or BackendConfig()
        self.workflow_storage = workflow_storage or SQLiteWorkflowStorage()
        self.event_storage = event_storage or SQLiteEventStorage()
        self.telemetry_storage = telemetry_storage or SQLiteTelemetryStorage()
        self.agent_execution_storage = agent_execution_storage or SQLiteAgentExecutionStorage()
        self.vector_memory_store = vector_memory_store or InMemoryVectorMemoryStore()
        self.worker = InlineWorker()

    def execute(self, question: str) -> OrchestrationExecution:
        execution = self.create_workflow(question)
        return self.run_workflow(execution.workflow_id)

    def create_workflow(self, question: str) -> OrchestrationExecution:
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
        return execution

    def run_workflow(self, workflow_id: str) -> OrchestrationExecution:
        try:
            self.start_workflow(workflow_id)
            for stage in WORKFLOW_STAGES:
                self.complete_stage(workflow_id, stage)
            return self.complete_workflow(workflow_id)
        except Exception:
            return self.fail_workflow(workflow_id)

    def start_workflow(self, workflow_id: str) -> OrchestrationExecution:
        return self._transition_workflow(workflow_id, "running")

    def complete_workflow(self, workflow_id: str) -> OrchestrationExecution:
        return self._transition_workflow(workflow_id, "completed")

    def fail_workflow(self, workflow_id: str) -> OrchestrationExecution:
        return self._transition_workflow(workflow_id, "failed")

    def complete_stage(self, workflow_id: str, stage: WorkflowStage) -> OrchestrationExecution:
        return self._transition_stage(workflow_id, stage)

    def get_workflow(self, workflow_id: str) -> OrchestrationExecution | None:
        workflow = self.workflow_storage.get(workflow_id)
        if workflow is None:
            return None

        telemetry = self.telemetry_storage.get(workflow.workflow_id) or workflow.telemetry
        agent_executions = self.agent_execution_storage.list(workflow.workflow_id)
        return OrchestrationExecution(
            workflow_id=workflow.workflow_id,
            question=workflow.question,
            status=workflow.status,
            created_at=workflow.created_at,
            telemetry=telemetry,
            current_stage=workflow.current_stage,
            stage_progression=workflow.stage_progression,
            agent_executions=agent_executions,
        )

    def get_events(self, workflow_id: str) -> tuple[WorkflowEvent, ...] | None:
        if self.get_workflow(workflow_id) is None:
            return None

        return self.event_storage.list(workflow_id)

    def get_stream_updates(self, workflow_id: str) -> tuple[WorkflowStreamUpdate, ...] | None:
        workflow = self.get_workflow(workflow_id)
        if workflow is None:
            return None

        updates: list[WorkflowStreamUpdate] = []
        events = self.get_events(workflow_id) or ()
        telemetry = self.telemetry_storage.get(workflow_id) or workflow.telemetry
        updates.extend(self._event_stream_updates(events))
        updates.extend(self._lifecycle_stream_updates(events))
        updates.extend(self._stage_stream_updates(workflow.stage_progression))
        updates.extend(self._agent_stream_updates(workflow.agent_executions, workflow.stage_progression))
        updates.extend(self._telemetry_stream_updates(telemetry))
        return tuple(sorted(updates, key=lambda update: update.timestamp))

    def _save_workflow(self, workflow: OrchestrationExecution) -> None:
        self.workflow_storage.save(workflow)
        self.telemetry_storage.save(workflow.workflow_id, workflow.telemetry)
        self.agent_execution_storage.save_all(workflow.workflow_id, workflow.agent_executions)

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
        self.event_storage.append(workflow_id, event)

    def _event_stream_updates(self, events: tuple[WorkflowEvent, ...]) -> list[WorkflowStreamUpdate]:
        return [
            WorkflowStreamUpdate(
                timestamp=event.timestamp,
                update_type="workflow_event",
                message=event.message,
                payload={
                    "event_type": event.event_type,
                    "message": event.message,
                    "timestamp": event.timestamp,
                },
            )
            for event in events
        ]

    def _lifecycle_stream_updates(self, events: tuple[WorkflowEvent, ...]) -> list[WorkflowStreamUpdate]:
        return [
            WorkflowStreamUpdate(
                timestamp=event.timestamp,
                update_type="lifecycle_transition",
                message=event.message,
                payload={
                    "event_type": event.event_type,
                    "message": event.message,
                    "timestamp": event.timestamp,
                },
            )
            for event in events
            if event.event_type == "lifecycle_transition"
        ]

    def _stage_stream_updates(
        self,
        stage_progression: tuple[WorkflowStageProgress, ...],
    ) -> list[WorkflowStreamUpdate]:
        return [
            WorkflowStreamUpdate(
                timestamp=stage.timestamp,
                update_type="stage_transition",
                message=f"Workflow stage completed: {stage.stage}.",
                payload={
                    "stage": stage.stage,
                    "status": stage.status,
                    "timestamp": stage.timestamp,
                },
            )
            for stage in stage_progression
        ]

    def _agent_stream_updates(
        self,
        agent_executions: tuple[AgentExecution, ...],
        stage_progression: tuple[WorkflowStageProgress, ...],
    ) -> list[WorkflowStreamUpdate]:
        stage_timestamps = {stage.stage: stage.timestamp for stage in stage_progression}
        return [
            WorkflowStreamUpdate(
                timestamp=stage_timestamps.get(agent.assigned_stage, datetime.now(timezone.utc).isoformat()),
                update_type="agent_update",
                message=f"Agent {agent.agent_name} completed {agent.assigned_stage}.",
                payload={
                    "agent_name": agent.agent_name,
                    "agent_role": agent.agent_role,
                    "assigned_stage": agent.assigned_stage,
                    "agent_status": agent.agent_status,
                },
            )
            for agent in agent_executions
        ]

    def _telemetry_stream_updates(self, telemetry: WorkflowTelemetry) -> list[WorkflowStreamUpdate]:
        updates: list[WorkflowStreamUpdate] = []
        if telemetry.started_at is not None:
            updates.append(
                WorkflowStreamUpdate(
                    timestamp=telemetry.started_at,
                    update_type="telemetry_update",
                    message="Workflow telemetry started.",
                    payload={"started_at": telemetry.started_at},
                )
            )
        if telemetry.completed_at is not None:
            updates.append(
                WorkflowStreamUpdate(
                    timestamp=telemetry.completed_at,
                    update_type="telemetry_update",
                    message="Workflow telemetry completed.",
                    payload={
                        "completed_at": telemetry.completed_at,
                        "latency_ms": telemetry.latency_ms,
                        "estimated_cost_usd": telemetry.estimated_cost_usd,
                        "token_usage": {
                            "prompt_tokens": telemetry.token_usage.prompt_tokens,
                            "completion_tokens": telemetry.token_usage.completion_tokens,
                            "total_tokens": telemetry.token_usage.total_tokens,
                        },
                    },
                )
            )
        return updates

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
