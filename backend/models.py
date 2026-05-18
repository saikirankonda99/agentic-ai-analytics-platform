from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


DEFAULT_USER_ID = "user:anonymous"
DEFAULT_WORKSPACE_ID = "workspace:default"

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
class Workspace:
    workspace_id: str
    name: str


@dataclass(frozen=True)
class RequestSession:
    user: User
    workspace: Workspace
    roles: tuple[str, ...] = ()

    @property
    def user_id(self) -> str:
        return self.user.user_id

    @property
    def workspace_id(self) -> str:
        return self.workspace.workspace_id


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


__all__ = [
    "AgentExecution",
    "AgentExecutionStatus",
    "AgentAssignedStage",
    "AgentCoordinationTrace",
    "DEFAULT_USER_ID",
    "DEFAULT_WORKSPACE_ID",
    "OrchestrationExecution",
    "RequestSession",
    "STAGE_AGENTS",
    "TokenUsage",
    "User",
    "WORKFLOW_STAGES",
    "Workspace",
    "WorkflowEvent",
    "WorkflowEventType",
    "WorkflowLifecycleState",
    "WorkflowStage",
    "WorkflowStageProgress",
    "WorkflowStreamUpdate",
    "WorkflowStreamUpdateType",
    "WorkflowTelemetry",
]
