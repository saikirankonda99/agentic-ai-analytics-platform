from __future__ import annotations

from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field

from backend.services import backend_service
from backend.models import RequestSession
from backend.routes import require_admin
from workspace import load_workspace_memory_by_id


app = FastAPI(
    title="Agentic Analytics Backend",
    version="0.2.0",
    description="Service layer for query orchestration, telemetry, investigations, and executive briefings.",
)


class QueryExecutionRequest(BaseModel):
    question: str
    semantic_context: dict[str, Any] | None = None
    conversation_context: dict[str, Any] | None = None
    workspace_context: dict[str, Any] | None = None


class InvestigationRequest(BaseModel):
    question: str
    sql: str
    insight_state: dict[str, Any] = Field(default_factory=dict)
    semantic_context: dict[str, Any] | None = None
    max_queries: int = 3


class ExecutiveBriefingRequest(BaseModel):
    targets: list[str] = Field(default_factory=lambda: ["revenue", "customers", "orders", "growth", "anomalies"])
    semantic_context: dict[str, Any] | None = None


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/query")
def execute_query(req: QueryExecutionRequest, session: RequestSession = Depends(require_admin)) -> dict[str, Any]:
    try:
        return backend_service.execute_query(
            req.question,
            semantic_context=req.semantic_context,
            conversation_context=req.conversation_context,
            workspace_context=load_workspace_memory_by_id(session.workspace_id, team_id=session.organization.name),
            workspace_id=session.workspace_id,
            organization_id=session.organization_id,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Query execution failed") from exc


@app.get("/workflow/status", dependencies=[Depends(require_admin)])
def workflow_status(run_id: str = "workflow:latest") -> dict[str, Any]:
    raise HTTPException(status_code=503, detail="Legacy workflow cache access is unavailable until workspace-scoped storage is implemented.")


@app.get("/telemetry", dependencies=[Depends(require_admin)])
def telemetry(run_id: str = "workflow:latest") -> dict[str, Any]:
    raise HTTPException(status_code=503, detail="Legacy telemetry cache access is unavailable until workspace-scoped storage is implemented.")


@app.post("/investigations")
def investigations(req: InvestigationRequest, session: RequestSession = Depends(require_admin)) -> dict[str, Any]:
    try:
        return backend_service.run_investigation(
            question=req.question,
            sql=req.sql,
            insight_state=req.insight_state,
            semantic_context=req.semantic_context,
            max_queries=req.max_queries,
            workspace_id=session.workspace_id,
            organization_id=session.organization_id,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Investigation failed") from exc


@app.post("/briefings")
def executive_briefings(req: ExecutiveBriefingRequest, session: RequestSession = Depends(require_admin)) -> dict[str, Any]:
    try:
        return backend_service.executive_briefing(
            targets=req.targets,
            semantic_context=req.semantic_context,
            workspace_id=session.workspace_id,
            organization_id=session.organization_id,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Briefing generation failed") from exc


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "agentic-analytics-backend", "status": "running"}
