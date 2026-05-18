from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.services import (
    AgentExecution,
    WorkflowEvent,
    WorkflowStageProgress,
    WorkflowTelemetry,
    orchestration_service,
)


SERVICE_NAME = "agentic-ai-analytics-backend"
SERVICE_VERSION = "0.1.0"
WorkflowStatus = Literal["queued", "running", "completed", "failed"]
AgentStatus = Literal["queued", "running", "completed", "failed"]
WorkflowStageName = Literal[
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

router = APIRouter(tags=["system"])


class ExecuteRequest(BaseModel):
    question: str = Field(..., min_length=1)


class TokenUsageResponse(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class WorkflowTelemetryResponse(BaseModel):
    started_at: str | None
    completed_at: str | None
    latency_ms: int | None
    estimated_cost_usd: float
    token_usage: TokenUsageResponse


class WorkflowStageProgressResponse(BaseModel):
    stage: WorkflowStageName
    status: WorkflowStatus
    timestamp: str


class WorkflowEventResponse(BaseModel):
    timestamp: str
    event_type: WorkflowEventType
    message: str


class AgentExecutionResponse(BaseModel):
    agent_name: str
    agent_role: str
    assigned_stage: WorkflowStageName
    agent_status: AgentStatus


class WorkflowEventsResponse(BaseModel):
    workflow_id: str
    events: list[WorkflowEventResponse]


class ExecuteResponse(BaseModel):
    workflow_id: str
    question: str
    status: WorkflowStatus
    timestamp: str
    telemetry: WorkflowTelemetryResponse
    current_stage: WorkflowStageName | None
    stage_progression: list[WorkflowStageProgressResponse]
    agent_executions: list[AgentExecutionResponse]


class WorkflowStatusResponse(BaseModel):
    workflow_id: str
    question: str
    status: WorkflowStatus
    created_at: str
    telemetry: WorkflowTelemetryResponse
    current_stage: WorkflowStageName | None
    stage_progression: list[WorkflowStageProgressResponse]
    agent_executions: list[AgentExecutionResponse]


@router.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": SERVICE_NAME,
        "version": SERVICE_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.post("/execute", response_model=ExecuteResponse)
def execute(payload: ExecuteRequest) -> ExecuteResponse:
    execution = orchestration_service.execute(payload.question)
    return ExecuteResponse(
        workflow_id=execution.workflow_id,
        question=execution.question,
        status=execution.status,
        timestamp=execution.created_at,
        telemetry=_telemetry_response(execution.telemetry),
        current_stage=execution.current_stage,
        stage_progression=_stage_progression_response(execution.stage_progression),
        agent_executions=_agent_executions_response(execution.agent_executions),
    )


@router.get("/workflow/{workflow_id}", response_model=WorkflowStatusResponse)
def get_workflow(workflow_id: str) -> WorkflowStatusResponse:
    workflow = orchestration_service.get_workflow(workflow_id)
    if workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found")

    return WorkflowStatusResponse(
        workflow_id=workflow.workflow_id,
        question=workflow.question,
        status=workflow.status,
        created_at=workflow.created_at,
        telemetry=_telemetry_response(workflow.telemetry),
        current_stage=workflow.current_stage,
        stage_progression=_stage_progression_response(workflow.stage_progression),
        agent_executions=_agent_executions_response(workflow.agent_executions),
    )


@router.get("/workflow/{workflow_id}/events", response_model=WorkflowEventsResponse)
def get_workflow_events(workflow_id: str) -> WorkflowEventsResponse:
    events = orchestration_service.get_events(workflow_id)
    if events is None:
        raise HTTPException(status_code=404, detail="Workflow not found")

    return WorkflowEventsResponse(
        workflow_id=workflow_id,
        events=_events_response(events),
    )


def _telemetry_response(telemetry: WorkflowTelemetry) -> WorkflowTelemetryResponse:
    return WorkflowTelemetryResponse(
        started_at=telemetry.started_at,
        completed_at=telemetry.completed_at,
        latency_ms=telemetry.latency_ms,
        estimated_cost_usd=telemetry.estimated_cost_usd,
        token_usage=TokenUsageResponse(
            prompt_tokens=telemetry.token_usage.prompt_tokens,
            completion_tokens=telemetry.token_usage.completion_tokens,
            total_tokens=telemetry.token_usage.total_tokens,
        ),
    )


def _stage_progression_response(
    stage_progression: tuple[WorkflowStageProgress, ...],
) -> list[WorkflowStageProgressResponse]:
    return [
        WorkflowStageProgressResponse(
            stage=stage.stage,
            status=stage.status,
            timestamp=stage.timestamp,
        )
        for stage in stage_progression
    ]


def _events_response(events: tuple[WorkflowEvent, ...]) -> list[WorkflowEventResponse]:
    return [
        WorkflowEventResponse(
            timestamp=event.timestamp,
            event_type=event.event_type,
            message=event.message,
        )
        for event in events
    ]


def _agent_executions_response(
    agent_executions: tuple[AgentExecution, ...],
) -> list[AgentExecutionResponse]:
    return [
        AgentExecutionResponse(
            agent_name=agent.agent_name,
            agent_role=agent.agent_role,
            assigned_stage=agent.assigned_stage,
            agent_status=agent.agent_status,
        )
        for agent in agent_executions
    ]


__all__ = ["router"]
