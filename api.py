from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from backend.services import backend_service


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
def execute_query(req: QueryExecutionRequest) -> dict[str, Any]:
    try:
        return backend_service.execute_query(
            req.question,
            semantic_context=req.semantic_context,
            conversation_context=req.conversation_context,
            workspace_context=req.workspace_context,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/workflow/status")
def workflow_status(run_id: str = "workflow:latest") -> dict[str, Any]:
    return backend_service.workflow_status(run_id)


@app.get("/telemetry")
def telemetry(run_id: str = "workflow:latest") -> dict[str, Any]:
    return backend_service.telemetry(run_id)


@app.post("/investigations")
def investigations(req: InvestigationRequest) -> dict[str, Any]:
    try:
        return backend_service.run_investigation(
            question=req.question,
            sql=req.sql,
            insight_state=req.insight_state,
            semantic_context=req.semantic_context,
            max_queries=req.max_queries,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/briefings")
def executive_briefings(req: ExecutiveBriefingRequest) -> dict[str, Any]:
    try:
        return backend_service.executive_briefing(
            targets=req.targets,
            semantic_context=req.semantic_context,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "agentic-analytics-backend", "status": "running"}
