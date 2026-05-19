from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


DEFAULT_USER_ID = "user:anonymous"
DEFAULT_ORGANIZATION_ID = "organization:default"
DEFAULT_WORKSPACE_ID = "workspace:default"
UsageEventType = Literal[
    "api_request",
    "workflow_execution",
    "token_usage",
    "estimated_ai_cost",
]

WorkflowLifecycleState = Literal["queued", "running", "retrying", "completed", "failed", "skipped"]
AgentExecutionStatus = Literal["queued", "running", "retrying", "completed", "failed", "skipped"]
WorkflowStage = Literal[
    "planning",
    "schema_analysis",
    "sql_generation",
    "validation",
    "execution",
    "insight_generation",
]
AgentAssignedStage = Literal[
    "planning",
    "schema_analysis",
    "sql_generation",
    "validation",
    "execution",
    "insight_generation",
    "reflection",
    "anomaly_detection",
    "investigation",
    "executive_briefing",
]
WorkflowEventType = Literal[
    "workflow_created",
    "lifecycle_transition",
    "stage_transition",
    "telemetry_update",
    "agent_handoff",
    "investigation_update",
]
WorkflowStreamUpdateType = Literal[
    "workflow_event",
    "lifecycle_transition",
    "stage_transition",
    "agent_update",
    "telemetry_update",
    "investigation_update",
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
class User:
    user_id: str
    email: str | None = None
    display_name: str | None = None


@dataclass(frozen=True)
class Organization:
    organization_id: str
    name: str
    plan: str = "free"


@dataclass(frozen=True)
class Workspace:
    workspace_id: str
    name: str
    organization_id: str = DEFAULT_ORGANIZATION_ID


@dataclass(frozen=True)
class WorkspaceMembership:
    user_id: str
    workspace_id: str
    organization_id: str
    roles: tuple[str, ...] = ("workspace:member",)


@dataclass(frozen=True)
class RequestSession:
    user: User
    organization: Organization
    workspace: Workspace
    membership: WorkspaceMembership
    roles: tuple[str, ...] = ()

    @property
    def user_id(self) -> str:
        return self.user.user_id

    @property
    def workspace_id(self) -> str:
        return self.workspace.workspace_id

    @property
    def organization_id(self) -> str:
        return self.organization.organization_id


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
    assigned_stage: AgentAssignedStage
    agent_status: AgentExecutionStatus


@dataclass(frozen=True)
class AgentCoordinationTrace:
    timestamp: str
    source_agent: str
    target_agent: str
    handoff_reason: str
    context_summary: str


@dataclass(frozen=True)
class WorkflowEvent:
    timestamp: str
    event_type: WorkflowEventType
    message: str


@dataclass(frozen=True)
class WorkflowStreamUpdate:
    timestamp: str
    update_type: WorkflowStreamUpdateType
    message: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class OrchestrationExecution:
    workflow_id: str
    workspace_id: str
    question: str
    status: WorkflowLifecycleState
    created_at: str
    telemetry: WorkflowTelemetry
    current_stage: WorkflowStage | None = None
    stage_progression: tuple[WorkflowStageProgress, ...] = ()
    agent_executions: tuple[AgentExecution, ...] = ()
    organization_id: str = DEFAULT_ORGANIZATION_ID
    user_id: str = DEFAULT_USER_ID


@dataclass(frozen=True)
class AnalyticsWorkflowResult:
    question: str
    effective_question: str
    sql: str
    columns: tuple[str, ...]
    rows: tuple[Any, ...]
    error: str | None
    trace: tuple[dict[str, Any], ...]
    telemetry: dict[str, Any]
    execution_graph: dict[str, Any] = field(default_factory=dict)
    stage_confidence: dict[str, float] = field(default_factory=dict)
    recovery: dict[str, Any] = field(default_factory=dict)
    policy_decision: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> "AnalyticsWorkflowResult":
        return cls(
            question=payload.get("question", ""),
            effective_question=payload.get("effective_question", payload.get("question", "")),
            sql=payload.get("sql", ""),
            columns=tuple(payload.get("columns", [])),
            rows=tuple(payload.get("rows", [])),
            error=payload.get("error"),
            trace=tuple(payload.get("trace", [])),
            telemetry=dict(payload.get("telemetry", {})),
            execution_graph=dict(payload.get("execution_graph", {})),
            stage_confidence=dict(payload.get("stage_confidence", {})),
            recovery=dict(payload.get("recovery", {})),
            policy_decision=dict(payload.get("policy_decision", {})),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "effective_question": self.effective_question,
            "sql": self.sql,
            "columns": list(self.columns),
            "rows": list(self.rows),
            "error": self.error,
            "trace": list(self.trace),
            "telemetry": self.telemetry,
            "execution_graph": self.execution_graph,
            "stage_confidence": self.stage_confidence,
            "recovery": self.recovery,
            "policy_decision": self.policy_decision,
        }


@dataclass(frozen=True)
class UsageRecord:
    usage_id: str
    organization_id: str
    workspace_id: str
    user_id: str
    event_type: UsageEventType
    quantity: float
    estimated_cost_usd: float
    timestamp: str
    metadata: dict[str, Any] = field(default_factory=dict)


__all__ = [
    "AgentExecution",
    "AgentExecutionStatus",
    "AgentAssignedStage",
    "AgentCoordinationTrace",
    "DEFAULT_ORGANIZATION_ID",
    "DEFAULT_USER_ID",
    "DEFAULT_WORKSPACE_ID",
    "AnalyticsWorkflowResult",
    "OrchestrationExecution",
    "Organization",
    "RequestSession",
    "STAGE_AGENTS",
    "TokenUsage",
    "UsageEventType",
    "UsageRecord",
    "User",
    "WORKFLOW_STAGES",
    "Workspace",
    "WorkspaceMembership",
    "WorkflowEvent",
    "WorkflowEventType",
    "WorkflowLifecycleState",
    "WorkflowStage",
    "WorkflowStageProgress",
    "WorkflowStreamUpdate",
    "WorkflowStreamUpdateType",
    "WorkflowTelemetry",
]
