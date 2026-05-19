from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timezone
from json import dumps
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from starlette.responses import StreamingResponse

from backend.auth_context import get_request_session
from backend.auth_sessions import login_user, revoke_session, validate_session_token
from backend.diagnostics import runtime_diagnostics
from backend.logging import get_logger
from backend.models import DEFAULT_ORGANIZATION_ID, DEFAULT_USER_ID, DEFAULT_WORKSPACE_ID, RequestSession
from backend.runtime import orchestration_runtime
from backend.services import (
    AgentCoordinationTrace,
    AgentExecution,
    WorkflowEvent,
    WorkflowStageProgress,
    WorkflowStreamUpdate,
    WorkflowTelemetry,
    backend_service,
    orchestration_service,
)
from backend.telemetry import RUNTIME_EVENT_TYPES, TELEMETRY_SCHEMA_VERSION, filter_telemetry_events, telemetry_aggregate
from backend.workspace_inspection import saved_sql_history, workflow_transcripts, workspace_summary
from backend.websocket import websocket_manager, workflow_channel
from workspace import (
    build_user_session,
    load_workspace_memory,
    load_workspace_memory_by_id,
    save_investigation_record,
    save_report_view,
    save_sql_history_record,
    save_workspace_memory,
    save_workspace_preferences,
)

logger = get_logger(__name__)

SERVICE_NAME = "agentic-ai-analytics-backend"
SERVICE_VERSION = "0.1.0"
WorkflowStatus = Literal["queued", "running", "retrying", "completed", "failed", "skipped"]
AgentStatus = Literal["queued", "running", "retrying", "completed", "failed", "skipped"]
WorkflowStageName = Literal[
    "planning",
    "schema_analysis",
    "sql_generation",
    "validation",
    "execution",
    "insight_generation",
]
AgentAssignedStageName = Literal[
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
    assigned_stage: AgentAssignedStageName
    agent_status: AgentStatus


class AgentCoordinationTraceResponse(BaseModel):
    timestamp: str
    source_agent: str
    target_agent: str
    handoff_reason: str
    context_summary: str


class WorkflowEventsResponse(BaseModel):
    workflow_id: str
    events: list[WorkflowEventResponse]


class WorkflowStreamUpdateResponse(BaseModel):
    timestamp: str
    update_type: WorkflowStreamUpdateType
    message: str
    payload: dict[str, object]


class ExecuteResponse(BaseModel):
    workflow_id: str
    question: str
    status: WorkflowStatus
    timestamp: str
    telemetry: WorkflowTelemetryResponse
    current_stage: WorkflowStageName | None
    stage_progression: list[WorkflowStageProgressResponse]
    agent_executions: list[AgentExecutionResponse]
    agent_traces: list[AgentCoordinationTraceResponse]


class WorkflowStatusResponse(BaseModel):
    workflow_id: str
    question: str
    status: WorkflowStatus
    created_at: str
    telemetry: WorkflowTelemetryResponse
    current_stage: WorkflowStageName | None
    stage_progression: list[WorkflowStageProgressResponse]
    agent_executions: list[AgentExecutionResponse]
    agent_traces: list[AgentCoordinationTraceResponse]


class WorkflowReplayResponse(BaseModel):
    workflow_id: str
    updates: list[WorkflowStreamUpdateResponse]


class WorkflowExecutionGraphResponse(BaseModel):
    workflow_id: str
    graph: dict[str, object]
    summary: dict[str, object]
    dependency_status: list[dict[str, object]]
    replay: dict[str, object]


class OperationsSummaryResponse(BaseModel):
    status: str
    readiness: dict[str, str]
    workflow_storage: str
    telemetry_schema_version: str


class ConnectorValidationRequest(BaseModel):
    connector_id: str = Field("sqlite", min_length=1)


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class LogoutRequest(BaseModel):
    session_token: str = Field(..., min_length=1)


class SavedSQLRequest(BaseModel):
    question: str = ""
    sql: str = Field(..., min_length=1)
    rows: int = 0
    intent: str = ""


class SavedInvestigationRequest(BaseModel):
    investigation: dict[str, object] = Field(default_factory=dict)
    note: str = ""


class WorkspacePreferencesRequest(BaseModel):
    preferences: dict[str, object] = Field(default_factory=dict)


class SavedReportRequest(BaseModel):
    title: str = Field("Workspace report", min_length=1)
    scope: str = "workspace"
    summary: str = ""
    payload: dict[str, object] = Field(default_factory=dict)


@router.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": SERVICE_NAME,
        "version": SERVICE_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/ready")
def readiness() -> dict[str, str]:
    return orchestration_service.readiness()


@router.get("/readiness")
def readiness_alias() -> dict[str, str]:
    return orchestration_service.readiness()


@router.get("/diagnostics")
def diagnostics() -> dict[str, object]:
    ready = orchestration_service.readiness()
    return runtime_diagnostics(ready)


@router.get("/operations/summary", response_model=OperationsSummaryResponse)
def operations_summary_endpoint() -> OperationsSummaryResponse:
    ready = orchestration_service.readiness()
    return OperationsSummaryResponse(
        status=ready.get("status", "unknown"),
        readiness=ready,
        workflow_storage=ready.get("workflow_storage", "unknown"),
        telemetry_schema_version=TELEMETRY_SCHEMA_VERSION,
    )


@router.post("/auth/login")
def login_endpoint(payload: LoginRequest) -> dict[str, object]:
    identity = login_user(payload.username, payload.password)
    if identity is None:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"authenticated": True, "session": identity}


@router.post("/auth/logout")
def logout_endpoint(payload: LogoutRequest) -> dict[str, object]:
    return {"revoked": revoke_session(payload.session_token)}


@router.get("/auth/session")
def auth_session(
    authorization: str | None = Header(default=None),
    x_session_token: str | None = Header(default=None),
    session: RequestSession = Depends(get_request_session),
) -> dict[str, object]:
    token = x_session_token or (authorization.removeprefix("Bearer ").strip() if authorization and authorization.startswith("Bearer ") else None)
    identity = validate_session_token(token)
    return {
        "authenticated": bool(identity),
        "session": identity,
        "request_session": {
            "user_id": session.user_id,
            "workspace_id": session.workspace_id,
            "organization_id": session.organization_id,
            "roles": list(session.roles),
        },
    }


@router.get("/governance")
def governance_center(session: RequestSession = Depends(get_request_session)) -> dict[str, object]:
    return backend_service.governance(session.workspace_id)


@router.get("/scheduler")
def scheduler_center(session: RequestSession = Depends(get_request_session)) -> dict[str, object]:
    return backend_service.scheduler(session.workspace_id)


@router.get("/incidents")
def incident_center(workflow_id: str = "workflow:latest") -> dict[str, object]:
    telemetry = backend_service.telemetry(workflow_id)
    return backend_service.incidents(telemetry, workflow_id=workflow_id)


@router.get("/executive/report")
def executive_report(workflow_id: str = "workflow:latest", session: RequestSession = Depends(get_request_session)) -> dict[str, object]:
    return backend_service.executive_report(
        workspace_id=session.workspace_id,
        telemetry=backend_service.telemetry(workflow_id),
    )


@router.get("/audit/timeline")
def audit_timeline(workflow_id: str = "workflow:latest", session: RequestSession = Depends(get_request_session)) -> dict[str, object]:
    return backend_service.operational_timeline(
        workspace_id=session.workspace_id,
        workflow_id=workflow_id,
        telemetry=backend_service.telemetry(workflow_id),
    )


@router.get("/connectors")
def list_connectors() -> dict[str, object]:
    return backend_service.connectors()


@router.get("/connectors/{connector_id}/health")
def connector_health(connector_id: str) -> dict[str, object]:
    try:
        return backend_service.connector_health(connector_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/connectors/{connector_id}/schema")
def connector_schema(connector_id: str) -> dict[str, object]:
    try:
        return backend_service.connector_schema(connector_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/connectors/validate")
def validate_connector(payload: ConnectorValidationRequest) -> dict[str, object]:
    try:
        return backend_service.validate_connector(payload.connector_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/connectors/{connector_id}/validate")
def validate_connector_by_id(connector_id: str) -> dict[str, object]:
    try:
        return backend_service.validate_connector(connector_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/execute", response_model=ExecuteResponse)
def execute(
    payload: ExecuteRequest,
    background_tasks: BackgroundTasks,
    session: RequestSession = Depends(get_request_session),
) -> ExecuteResponse:
    try:
        orchestration_service.register_session(session)
        execution = orchestration_runtime.submit(
            payload.question,
            background_tasks,
            organization_id=session.organization_id,
            workspace_id=session.workspace_id,
            user_id=session.user_id,
        )
    except Exception as exc:
        logger.exception("execute_request_failed workspace_id=%s", session.workspace_id)
        raise HTTPException(status_code=500, detail="Workflow execution could not be started") from exc
    return ExecuteResponse(
        workflow_id=execution.workflow_id,
        question=execution.question,
        status=execution.status,
        timestamp=execution.created_at,
        telemetry=_telemetry_response(execution.telemetry),
        current_stage=execution.current_stage,
        stage_progression=_stage_progression_response(execution.stage_progression),
        agent_executions=_agent_executions_response(execution.agent_executions),
        agent_traces=_agent_traces_response(orchestration_service.get_agent_traces(execution.workflow_id) or ()),
    )


@router.get("/workflow/{workflow_id}", response_model=WorkflowStatusResponse)
def get_workflow(workflow_id: str) -> WorkflowStatusResponse:
    workflow = orchestration_service.get_workflow(workflow_id)
    if workflow is None:
        logger.info("workflow_not_found workflow_id=%s", workflow_id)
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
        agent_traces=_agent_traces_response(orchestration_service.get_agent_traces(workflow_id) or ()),
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


@router.get("/workflow/{workflow_id}/telemetry", response_model=WorkflowTelemetryResponse)
def get_workflow_telemetry(workflow_id: str) -> WorkflowTelemetryResponse:
    workflow = orchestration_service.get_workflow(workflow_id)
    if workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return _telemetry_response(workflow.telemetry)


@router.get("/workflow/{workflow_id}/replay", response_model=WorkflowReplayResponse)
def replay_workflow(workflow_id: str) -> WorkflowReplayResponse:
    updates = orchestration_service.get_stream_updates(workflow_id)
    if updates is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return WorkflowReplayResponse(
        workflow_id=workflow_id,
        updates=[WorkflowStreamUpdateResponse(**_stream_update_payload(update)) for update in updates],
    )


@router.get("/workflow/{workflow_id}/execution-graph", response_model=WorkflowExecutionGraphResponse)
def get_workflow_execution_graph(workflow_id: str) -> WorkflowExecutionGraphResponse:
    graph = orchestration_service.get_execution_graph(workflow_id)
    if graph is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return WorkflowExecutionGraphResponse(**graph)


@router.get("/telemetry/schema")
def telemetry_schema() -> dict[str, object]:
    return {
        "schema_version": TELEMETRY_SCHEMA_VERSION,
        "event_types": list(RUNTIME_EVENT_TYPES),
    }


@router.get("/workflow/{workflow_id}/telemetry/events")
def workflow_telemetry_events(workflow_id: str, q: str = "", phase: str = "", status: str = "") -> dict[str, object]:
    updates = orchestration_service.get_stream_updates(workflow_id)
    if updates is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    events = [
        {
            "timestamp": update.timestamp,
            "phase": update.payload.get("stage") or update.payload.get("event_type") or update.update_type,
            "status": update.payload.get("status") or update.payload.get("agent_status") or update.update_type,
            "message": update.message,
            "payload": update.payload,
        }
        for update in updates
    ]
    return {"workflow_id": workflow_id, "events": filter_telemetry_events(events, query=q, phase=phase, status=status)}


@router.get("/workflow/{workflow_id}/telemetry/aggregate")
def workflow_telemetry_aggregate(workflow_id: str) -> dict[str, object]:
    updates = orchestration_service.get_stream_updates(workflow_id)
    if updates is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    events = [
        {
            "timestamp": update.timestamp,
            "phase": update.payload.get("stage") or update.payload.get("event_type") or update.update_type,
            "status": update.payload.get("status") or update.payload.get("agent_status") or update.update_type,
            "message": update.message,
            **{
                key: update.payload.get(key)
                for key in ("latency_ms", "total_tokens", "cost_usd", "error_type", "error_message")
                if key in update.payload
            },
        }
        for update in updates
    ]
    return {"workflow_id": workflow_id, "aggregate": telemetry_aggregate(events)}


@router.get("/investigations/latest")
def latest_investigation() -> dict[str, object]:
    return backend_service.cache.get("investigation:latest") or {
        "status": "empty",
        "summary": "No investigation has been persisted in the current backend process.",
    }


@router.get("/workspace/{workspace_id}/inspection")
def inspect_workspace(workspace_id: str) -> dict[str, object]:
    memory = load_workspace_memory_by_id(workspace_id)
    return workspace_summary(memory)


@router.get("/workspace/{workspace_id}")
def get_workspace_memory(workspace_id: str, session: RequestSession = Depends(get_request_session)) -> dict[str, object]:
    _ensure_workspace_access(session, workspace_id)
    return load_workspace_memory_by_id(workspace_id)


@router.post("/workspace/{workspace_id}/sql-history")
def save_workspace_sql_history(
    workspace_id: str,
    payload: SavedSQLRequest,
    session: RequestSession = Depends(get_request_session),
) -> dict[str, object]:
    _ensure_workspace_access(session, workspace_id)
    identity = build_user_session(session.user_id, session.workspace_id.split(".", 1)[0], "admin", session.user.display_name)
    identity["workspace_id"] = workspace_id
    memory = load_workspace_memory(identity)
    memory = save_sql_history_record(
        memory,
        question=payload.question,
        sql=payload.sql,
        rows=payload.rows,
        intent=payload.intent,
    )
    memory = save_workspace_memory(identity, memory)
    return {"workspace_id": workspace_id, "items": saved_sql_history(memory)}


@router.post("/workspace/{workspace_id}/investigations")
def save_workspace_investigation(
    workspace_id: str,
    payload: SavedInvestigationRequest,
    session: RequestSession = Depends(get_request_session),
) -> dict[str, object]:
    _ensure_workspace_access(session, workspace_id)
    identity = build_user_session(session.user_id, session.workspace_id.split(".", 1)[0], "admin", session.user.display_name)
    identity["workspace_id"] = workspace_id
    memory = load_workspace_memory(identity)
    memory = save_investigation_record(memory, dict(payload.investigation), note=payload.note)
    memory = save_workspace_memory(identity, memory)
    return {"workspace_id": workspace_id, "investigations": memory.get("investigations", [])}


@router.post("/workspace/{workspace_id}/preferences")
def save_workspace_preferences_endpoint(
    workspace_id: str,
    payload: WorkspacePreferencesRequest,
    session: RequestSession = Depends(get_request_session),
) -> dict[str, object]:
    _ensure_workspace_access(session, workspace_id)
    identity = build_user_session(session.user_id, session.workspace_id.split(".", 1)[0], "admin", session.user.display_name)
    identity["workspace_id"] = workspace_id
    memory = load_workspace_memory(identity)
    memory = save_workspace_preferences(memory, dict(payload.preferences))
    memory = save_workspace_memory(identity, memory)
    return {"workspace_id": workspace_id, "preferences": memory.get("workspace_preferences", {})}


@router.post("/workspace/{workspace_id}/reports")
def save_workspace_report(
    workspace_id: str,
    payload: SavedReportRequest,
    session: RequestSession = Depends(get_request_session),
) -> dict[str, object]:
    _ensure_workspace_access(session, workspace_id)
    identity = build_user_session(session.user_id, session.workspace_id.split(".", 1)[0], "admin", session.user.display_name)
    identity["workspace_id"] = workspace_id
    memory = load_workspace_memory(identity)
    memory = save_report_view(
        memory,
        {"title": payload.title, "scope": payload.scope, "summary": payload.summary, "payload": payload.payload},
    )
    memory = save_workspace_memory(identity, memory)
    return {"workspace_id": workspace_id, "reports": memory.get("saved_reports", [])}


@router.get("/workspace/{workspace_id}/transcripts")
def export_workspace_transcripts(workspace_id: str, session_id: str = "") -> dict[str, object]:
    memory = load_workspace_memory_by_id(workspace_id)
    return {
        "workspace_id": memory.get("workspace_id", workspace_id),
        "session_id": session_id or None,
        "transcripts": workflow_transcripts(memory, session_id=session_id or None),
    }


@router.get("/workspace/{workspace_id}/sql-history")
def export_workspace_sql_history(workspace_id: str, limit: int = 25) -> dict[str, object]:
    memory = load_workspace_memory_by_id(workspace_id)
    return {
        "workspace_id": memory.get("workspace_id", workspace_id),
        "items": saved_sql_history(memory, limit=max(1, min(limit, 100))),
    }


@router.get("/workflow/{workflow_id}/stream")
def stream_workflow_updates(workflow_id: str) -> StreamingResponse:
    updates = orchestration_service.get_stream_updates(workflow_id)
    if updates is None:
        raise HTTPException(status_code=404, detail="Workflow not found")

    return StreamingResponse(
        _sse_stream(updates),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.websocket("/workflow/{workflow_id}/ws")
async def websocket_workflow_updates(websocket: WebSocket, workflow_id: str) -> None:
    workflow = orchestration_service.get_workflow(workflow_id)
    if workflow is None:
        await websocket.close(code=1008)
        return

    organization_id = websocket.headers.get("x-organization-id") or DEFAULT_ORGANIZATION_ID
    workspace_id = websocket.headers.get("x-workspace-id") or DEFAULT_WORKSPACE_ID
    if workflow.organization_id != organization_id:
        await websocket.close(code=1008)
        return
    if workflow.workspace_id != workspace_id:
        await websocket.close(code=1008)
        return

    channel = workflow_channel(workflow_id, workspace_id, organization_id)
    await websocket_manager.connect(websocket, channel)
    try:
        for update in orchestration_service.get_stream_updates(workflow_id) or ():
            await websocket.send_text(dumps(_stream_update_payload(update)))
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        websocket_manager.disconnect(websocket, channel)
    except RuntimeError:
        websocket_manager.disconnect(websocket, channel)


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


def _ensure_workspace_access(session: RequestSession, workspace_id: str) -> None:
    if session.user_id == DEFAULT_USER_ID:
        raise HTTPException(status_code=401, detail="Authentication required")
    if session.workspace_id != workspace_id:
        raise HTTPException(status_code=403, detail="Workspace access denied")


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


def _agent_traces_response(traces: tuple[AgentCoordinationTrace, ...]) -> list[AgentCoordinationTraceResponse]:
    return [
        AgentCoordinationTraceResponse(
            timestamp=trace.timestamp,
            source_agent=trace.source_agent,
            target_agent=trace.target_agent,
            handoff_reason=trace.handoff_reason,
            context_summary=trace.context_summary,
        )
        for trace in traces
    ]


def _sse_stream(updates: tuple[WorkflowStreamUpdate, ...]) -> Iterator[str]:
    for update in updates:
        yield f"event: {update.update_type}\n"
        yield f"data: {dumps(_stream_update_payload(update))}\n\n"


def _stream_update_payload(update: WorkflowStreamUpdate) -> dict[str, object]:
    event = WorkflowStreamUpdateResponse(
        timestamp=update.timestamp,
        update_type=update.update_type,
        message=update.message,
        payload=update.payload,
    )
    return event.model_dump()


__all__ = ["router"]
