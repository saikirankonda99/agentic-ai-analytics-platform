from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Callable
from uuid import uuid4

from backend.agents import MultiAgentCoordinator
from backend.audit import audit_log_from_workflow, operational_timeline
from backend.connectors import ConnectorRegistry, get_connector_registry
from backend.execution_graph import execution_graph_response
from backend.executive import operational_report
from backend.governance import governance_overview
from backend.incidents import incident_from_telemetry, incident_overview
from backend.logging import get_logger
from backend.memory import MemoryDocument, VectorMemoryStore, build_vector_memory_store
from backend.models import (
    AnalyticsWorkflowResult,
    DEFAULT_ORGANIZATION_ID,
    DEFAULT_USER_ID,
    DEFAULT_WORKSPACE_ID,
    WORKFLOW_STAGES,
    AgentCoordinationTrace,
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
    RequestSession,
)
from backend.ports import BackendConfig, InMemoryCache, InlineWorker
from backend.storage import (
    AccountStorage,
    AgentExecutionStorage,
    AgentTraceStorage,
    EventStorage,
    TelemetryStorage,
    UsageStorage,
    WorkflowStorage,
    build_account_storage,
    build_agent_execution_storage,
    build_agent_trace_storage,
    build_event_storage,
    build_telemetry_storage,
    build_workflow_storage,
)
from backend.scheduler import scheduler_overview
from backend.usage import UsageService, usage_service
from backend.telemetry import validate_telemetry_payload


if TYPE_CHECKING:
    from graph.workflow import WorkflowState


WorkflowCallback = Callable[[str, "WorkflowState", str, str], None]
logger = get_logger(__name__)


class OrchestrationService:
    def __init__(
        self,
        config: BackendConfig | None = None,
        workflow_storage: WorkflowStorage | None = None,
        account_storage: AccountStorage | None = None,
        event_storage: EventStorage | None = None,
        telemetry_storage: TelemetryStorage | None = None,
        agent_execution_storage: AgentExecutionStorage | None = None,
        agent_trace_storage: AgentTraceStorage | None = None,
        usage_storage: UsageStorage | None = None,
        usage: UsageService | None = None,
        vector_memory_store: VectorMemoryStore | None = None,
        agent_coordinator: MultiAgentCoordinator | None = None,
        connector_registry: ConnectorRegistry | None = None,
    ) -> None:
        self.config = config or BackendConfig()
        self.workflow_storage = workflow_storage or build_workflow_storage()
        self.account_storage = account_storage or build_account_storage()
        self.event_storage = event_storage or build_event_storage()
        self.telemetry_storage = telemetry_storage or build_telemetry_storage()
        self.agent_execution_storage = agent_execution_storage or build_agent_execution_storage()
        self.agent_trace_storage = agent_trace_storage or build_agent_trace_storage()
        self.usage_service = usage or (UsageService(usage_storage=usage_storage) if usage_storage else usage_service)
        self.vector_memory_store = vector_memory_store or build_vector_memory_store()
        self.agent_coordinator = agent_coordinator or MultiAgentCoordinator()
        self.connector_registry = connector_registry or get_connector_registry()
        self.worker = InlineWorker()

    def register_session(self, session: RequestSession) -> None:
        self.account_storage.save_organization(session.organization)
        self.account_storage.save_workspace(session.workspace)
        self.account_storage.save_membership(session.membership)

    def execute(
        self,
        question: str,
        workspace_id: str = DEFAULT_WORKSPACE_ID,
        organization_id: str = DEFAULT_ORGANIZATION_ID,
        user_id: str = DEFAULT_USER_ID,
    ) -> OrchestrationExecution:
        execution = self.create_workflow(
            question,
            workspace_id=workspace_id,
            organization_id=organization_id,
            user_id=user_id,
        )
        return self.run_workflow(execution.workflow_id)

    def create_workflow(
        self,
        question: str,
        workspace_id: str = DEFAULT_WORKSPACE_ID,
        organization_id: str = DEFAULT_ORGANIZATION_ID,
        user_id: str = DEFAULT_USER_ID,
    ) -> OrchestrationExecution:
        execution = OrchestrationExecution(
            workflow_id=f"workflow:{uuid4()}",
            organization_id=organization_id,
            workspace_id=workspace_id,
            user_id=user_id,
            question=question,
            status="queued",
            created_at=datetime.now(timezone.utc).isoformat(),
            telemetry=WorkflowTelemetry(),
        )
        self._save_workflow(execution)
        logger.info(
            "workflow_created workflow_id=%s workspace_id=%s",
            execution.workflow_id,
            execution.workspace_id,
        )
        self.usage_service.record(
            "workflow_execution",
            organization_id=execution.organization_id,
            workspace_id=execution.workspace_id,
            user_id=execution.user_id,
            metadata={"workflow_id": execution.workflow_id},
        )
        self._append_event(
            execution.workflow_id,
            "workflow_created",
            f"Workflow created for question: {question}",
            organization_id=execution.organization_id,
            workspace_id=execution.workspace_id,
        )
        self.vector_memory_store.upsert(
            MemoryDocument(
                namespace="workflow_context",
                text=question,
                organization_id=execution.organization_id,
                workspace_id=execution.workspace_id,
                metadata={"workflow_id": execution.workflow_id},
            )
        )
        return execution

    def readiness(self) -> dict[str, str]:
        checks = {
            "account_storage": self._check_dependency(lambda: self.account_storage.get_workspace("__readiness__")),
            "workflow_storage": self._check_dependency(lambda: self.workflow_storage.get("workflow:latest")),
            "event_storage": self._check_dependency(lambda: self.event_storage.list("__readiness__")),
            "telemetry_storage": self._check_dependency(lambda: self.telemetry_storage.get("__readiness__")),
            "agent_execution_storage": self._check_dependency(
                lambda: self.agent_execution_storage.list("__readiness__")
            ),
            "agent_trace_storage": self._check_dependency(lambda: self.agent_trace_storage.list("__readiness__")),
            "usage_storage": self._check_dependency(lambda: self.usage_service.list_usage(workspace_id="__readiness__")),
            "vector_memory": "ok",
            "sqlite_connector": "ok" if self.connector_registry.health("sqlite").get("status") == "healthy" else "error",
        }
        checks["status"] = "ready" if all(value == "ok" for value in checks.values()) else "degraded"
        return checks

    def _check_dependency(self, check: Callable[[], object]) -> str:
        try:
            check()
        except Exception:
            logger.exception("readiness_check_failed")
            return "error"
        return "ok"

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
        agent_executions = self.agent_execution_storage.list(
            workflow.workflow_id,
            workspace_id=workflow.workspace_id,
        )
        return OrchestrationExecution(
            workflow_id=workflow.workflow_id,
            organization_id=workflow.organization_id,
            workspace_id=workflow.workspace_id,
            user_id=workflow.user_id,
            question=workflow.question,
            status=workflow.status,
            created_at=workflow.created_at,
            telemetry=telemetry,
            current_stage=workflow.current_stage,
            stage_progression=workflow.stage_progression,
            agent_executions=agent_executions,
        )

    def get_events(self, workflow_id: str) -> tuple[WorkflowEvent, ...] | None:
        workflow = self.get_workflow(workflow_id)
        if workflow is None:
            return None

        return self.event_storage.list(workflow_id, workspace_id=workflow.workspace_id)

    def get_agent_traces(self, workflow_id: str) -> tuple[AgentCoordinationTrace, ...] | None:
        workflow = self.get_workflow(workflow_id)
        if workflow is None:
            return None

        return self.agent_trace_storage.list(workflow_id, workspace_id=workflow.workspace_id)

    def get_stream_updates(self, workflow_id: str) -> tuple[WorkflowStreamUpdate, ...] | None:
        workflow = self.get_workflow(workflow_id)
        if workflow is None:
            return None

        updates: list[WorkflowStreamUpdate] = []
        events = self.get_events(workflow_id) or ()
        telemetry = self.telemetry_storage.get(workflow_id) or workflow.telemetry
        updates.extend(self._event_stream_updates(events))
        updates.extend(self._lifecycle_stream_updates(events))
        updates.extend(self._investigation_stream_updates(events))
        updates.extend(self._stage_stream_updates(workflow.stage_progression))
        updates.extend(self._agent_stream_updates(workflow.agent_executions, workflow.stage_progression))
        updates.extend(self._telemetry_stream_updates(telemetry))
        return tuple(sorted(updates, key=lambda update: update.timestamp))

    def get_execution_graph(self, workflow_id: str) -> dict[str, Any] | None:
        workflow = self.get_workflow(workflow_id)
        if workflow is None:
            return None
        return execution_graph_response(workflow, self.get_stream_updates(workflow_id) or ())

    def _save_workflow(self, workflow: OrchestrationExecution) -> None:
        self.workflow_storage.save(workflow)
        self.telemetry_storage.save(
            workflow.workflow_id,
            workflow.telemetry,
            organization_id=workflow.organization_id,
            workspace_id=workflow.workspace_id,
        )
        self.agent_execution_storage.save_all(
            workflow.workflow_id,
            workflow.agent_executions,
            organization_id=workflow.organization_id,
            workspace_id=workflow.workspace_id,
        )

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
            organization_id=workflow.organization_id,
            workspace_id=workflow.workspace_id,
            user_id=workflow.user_id,
            question=workflow.question,
            status=status,
            created_at=workflow.created_at,
            telemetry=self._build_telemetry(workflow, status),
            current_stage=workflow.current_stage,
            stage_progression=workflow.stage_progression,
            agent_executions=workflow.agent_executions,
        )
        self._save_workflow(updated)
        logger.info("workflow_lifecycle_transition workflow_id=%s status=%s", workflow_id, status)
        self._append_event(
            workflow_id,
            "lifecycle_transition",
            f"Workflow status changed to {status}.",
            organization_id=workflow.organization_id,
            workspace_id=workflow.workspace_id,
        )
        if updated.telemetry != workflow.telemetry:
            self._append_event(
                workflow_id,
                "telemetry_update",
                f"Workflow telemetry updated for {status} status.",
                organization_id=workflow.organization_id,
                workspace_id=workflow.workspace_id,
            )
            if status in {"completed", "failed"}:
                self._record_telemetry_usage(updated)
        return updated

    def _transition_stage(
        self,
        workflow_id: str,
        stage: WorkflowStage,
    ) -> OrchestrationExecution:
        workflow = self.get_workflow(workflow_id)
        if workflow is None:
            raise ValueError(f"Workflow not found: {workflow_id}")

        coordination = self.agent_coordinator.coordinate_stage(stage, workflow.question)
        traces = (*self.agent_trace_storage.list(workflow_id, workspace_id=workflow.workspace_id), *coordination.traces)
        updated = OrchestrationExecution(
            workflow_id=workflow.workflow_id,
            organization_id=workflow.organization_id,
            workspace_id=workflow.workspace_id,
            user_id=workflow.user_id,
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
                *coordination.executions,
            ),
        )
        self._save_workflow(updated)
        logger.info("workflow_stage_completed workflow_id=%s stage=%s", workflow_id, stage)
        self.agent_trace_storage.save_all(
            workflow_id,
            traces,
            organization_id=workflow.organization_id,
            workspace_id=workflow.workspace_id,
        )
        for trace in coordination.traces:
            self._append_event(
                workflow_id,
                "agent_handoff",
                f"{trace.source_agent} handed off to {trace.target_agent}.",
                organization_id=workflow.organization_id,
                workspace_id=workflow.workspace_id,
            )
        if stage == "insight_generation":
            self._append_event(
                workflow_id,
                "investigation_update",
                "Anomaly detection triggered an autonomous investigation chain.",
                organization_id=workflow.organization_id,
                workspace_id=workflow.workspace_id,
            )
            self.vector_memory_store.upsert(
                MemoryDocument(
                    namespace="investigation",
                    text=f"Autonomous investigation chain for {workflow.question}",
                    organization_id=workflow.organization_id,
                    workspace_id=workflow.workspace_id,
                    metadata={"workflow_id": workflow.workflow_id},
                )
            )
        self._append_event(
            workflow_id,
            "stage_transition",
            f"Workflow stage completed: {stage}.",
            organization_id=workflow.organization_id,
            workspace_id=workflow.workspace_id,
        )
        return updated

    def _append_event(
        self,
        workflow_id: str,
        event_type: WorkflowEventType,
        message: str,
        workspace_id: str,
        organization_id: str = DEFAULT_ORGANIZATION_ID,
    ) -> None:
        event = WorkflowEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            event_type=event_type,
            message=message,
        )
        self.event_storage.append(
            workflow_id,
            event,
            organization_id=organization_id,
            workspace_id=workspace_id,
        )

    def _record_telemetry_usage(self, workflow: OrchestrationExecution) -> None:
        token_usage = workflow.telemetry.token_usage
        if token_usage.total_tokens:
            self.usage_service.record(
                "token_usage",
                organization_id=workflow.organization_id,
                workspace_id=workflow.workspace_id,
                user_id=workflow.user_id,
                quantity=float(token_usage.total_tokens),
                metadata={"workflow_id": workflow.workflow_id},
            )
        if workflow.telemetry.estimated_cost_usd:
            self.usage_service.record(
                "estimated_ai_cost",
                organization_id=workflow.organization_id,
                workspace_id=workflow.workspace_id,
                user_id=workflow.user_id,
                quantity=workflow.telemetry.estimated_cost_usd,
                estimated_cost_usd=workflow.telemetry.estimated_cost_usd,
                metadata={"workflow_id": workflow.workflow_id},
            )

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

    def _investigation_stream_updates(self, events: tuple[WorkflowEvent, ...]) -> list[WorkflowStreamUpdate]:
        return [
            WorkflowStreamUpdate(
                timestamp=event.timestamp,
                update_type="investigation_update",
                message=event.message,
                payload={
                    "event_type": event.event_type,
                    "message": event.message,
                    "timestamp": event.timestamp,
                },
            )
            for event in events
            if event.event_type == "investigation_update"
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
        self.vector_memory_store = build_vector_memory_store()
        self.connector_registry = get_connector_registry()

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
        raw_result = run_workflow(
            question,
            callback=callback,
            semantic_context=workflow_context,
            conversation_context=conversation_context,
            workspace_context=workspace_context,
        )
        raw_result["telemetry"] = validate_telemetry_payload(raw_result.get("telemetry", {}))
        result = AnalyticsWorkflowResult.from_mapping(raw_result).as_dict()
        run_id = f"workflow:{datetime.now().isoformat(timespec='seconds')}"
        self.cache.set(run_id, result)
        self.cache.set("workflow:latest", result)
        return dict(result)

    def workflow_status(self, run_id: str = "workflow:latest") -> dict[str, Any]:
        return self.cache.get(run_id) or {}

    def telemetry(self, run_id: str = "workflow:latest") -> dict[str, Any]:
        return (self.workflow_status(run_id) or {}).get("telemetry", {})

    def profile_result(
        self,
        columns: list[str],
        rows: list[Any],
        name: str,
        workspace_id: str = DEFAULT_WORKSPACE_ID,
        organization_id: str = DEFAULT_ORGANIZATION_ID,
    ) -> dict[str, Any]:
        import pandas as pd
        from semantic import profile_dataframe

        profile = profile_dataframe(pd.DataFrame(rows, columns=columns), name=name)
        self.vector_memory_store.upsert(
            MemoryDocument(
                namespace="semantic_dataset_summary",
                text=f"{name}: {profile}",
                organization_id=organization_id,
                workspace_id=workspace_id,
                metadata={"dataset_name": name},
            )
        )
        return profile

    def run_investigation(
        self,
        *,
        question: str,
        sql: str,
        insight_state: dict[str, Any],
        semantic_context: dict[str, Any] | None = None,
        max_queries: int = 3,
        workspace_id: str = DEFAULT_WORKSPACE_ID,
        organization_id: str = DEFAULT_ORGANIZATION_ID,
    ) -> dict[str, Any]:
        from investigation import run_investigation

        result = run_investigation(question, sql, insight_state, semantic_context, max_queries=max_queries)
        self.cache.set("investigation:latest", result)
        self.vector_memory_store.upsert(
            MemoryDocument(
                namespace="investigation",
                text=f"{question}: {result}",
                organization_id=organization_id,
                workspace_id=workspace_id,
                metadata={"sql": sql},
            )
        )
        return result

    def executive_briefing(
        self,
        *,
        targets: list[str],
        semantic_context: dict[str, Any] | None = None,
        workspace_id: str = DEFAULT_WORKSPACE_ID,
        organization_id: str = DEFAULT_ORGANIZATION_ID,
    ) -> dict[str, Any]:
        from monitoring import run_monitoring_checks

        monitoring_state, briefing = run_monitoring_checks(targets, semantic_context)
        self.cache.set("monitoring:latest", monitoring_state)
        self.cache.set("briefing:latest", briefing)
        self.vector_memory_store.upsert(
            MemoryDocument(
                namespace="executive_insight",
                text=f"{targets}: {briefing}",
                organization_id=organization_id,
                workspace_id=workspace_id,
                metadata={"targets": targets},
            )
        )
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
        columns, rows = self.connector_registry.get("sqlite").execute_read(sql)
        return {"columns": columns, "rows": rows, "count": len(rows)}

    def connectors(self) -> dict[str, Any]:
        return {"connectors": self.connector_registry.list_connectors()}

    def connector_health(self, connector_id: str) -> dict[str, Any]:
        return self.connector_registry.health(connector_id)

    def validate_connector(self, connector_id: str) -> dict[str, Any]:
        return self.connector_registry.validate(connector_id)

    def connector_schema(self, connector_id: str) -> dict[str, Any]:
        return self.connector_registry.inspect_schema(connector_id)

    def governance(self, workspace_id: str = DEFAULT_WORKSPACE_ID) -> dict[str, Any]:
        return governance_overview(workspace_id)

    def scheduler(self, workspace_id: str = DEFAULT_WORKSPACE_ID) -> dict[str, Any]:
        return scheduler_overview(workspace_id)

    def incidents(self, telemetry: dict[str, Any] | None = None, workflow_id: str | None = None) -> dict[str, Any]:
        incident = incident_from_telemetry(telemetry, workflow_id=workflow_id)
        return incident_overview([incident] if incident else [])

    def executive_report(
        self,
        *,
        workspace_id: str = DEFAULT_WORKSPACE_ID,
        telemetry: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        governance = self.governance(workspace_id)
        scheduler = self.scheduler(workspace_id)
        incidents = self.incidents(telemetry)
        return operational_report(
            workspace_id=workspace_id,
            governance=governance,
            scheduler=scheduler,
            telemetry=telemetry or {},
            incidents=incidents,
        )

    def operational_timeline(
        self,
        *,
        workspace_id: str = DEFAULT_WORKSPACE_ID,
        workflow_id: str = "workflow:latest",
        telemetry: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        workflow = orchestration_service.get_workflow(workflow_id)
        workflow_audit = None
        if workflow is not None:
            workflow_audit = audit_log_from_workflow(
                workflow,
                orchestration_service.get_events(workflow.workflow_id) or (),
                orchestration_service.get_stream_updates(workflow.workflow_id) or (),
            )
        incidents = self.incidents(telemetry, workflow_id=None).get("incidents", [])
        schedules = self.scheduler(workspace_id).get("schedules", [])
        return {
            "workspace_id": workspace_id,
            "workflow_id": workflow.workflow_id if workflow else None,
            "timeline": operational_timeline(
                workflow_audit=workflow_audit,
                incidents=incidents,
                schedules=schedules,
            ),
        }


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
