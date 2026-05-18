from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter
from pydantic import BaseModel, Field


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
    return ExecuteResponse(
        workflow_id=f"workflow:{uuid4()}",
        question=payload.question,
        status="accepted",
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


__all__ = ["router"]
