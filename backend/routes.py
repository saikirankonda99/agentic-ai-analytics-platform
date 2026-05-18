from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.services import orchestration_service


SERVICE_NAME = "agentic-ai-analytics-backend"
SERVICE_VERSION = "0.1.0"

router = APIRouter(tags=["system"])


class ExecuteRequest(BaseModel):
    question: str = Field(..., min_length=1)


class ExecuteResponse(BaseModel):
    workflow_id: str
    question: str
    status: str
    timestamp: str


class WorkflowStatusResponse(BaseModel):
    workflow_id: str
    question: str
    status: str
    created_at: str


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
    )


__all__ = ["router"]
