from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter


SERVICE_NAME = "agentic-ai-analytics-backend"
SERVICE_VERSION = "0.1.0"

router = APIRouter(tags=["system"])


@router.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": SERVICE_NAME,
        "version": SERVICE_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


__all__ = ["router"]
