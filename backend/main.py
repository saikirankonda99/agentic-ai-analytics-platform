from __future__ import annotations

from datetime import datetime, timezone

from fastapi import FastAPI


SERVICE_NAME = "agentic-ai-analytics-backend"
SERVICE_VERSION = "0.1.0"

app = FastAPI(
    title="Agentic AI Analytics Backend",
    version=SERVICE_VERSION,
)


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": SERVICE_NAME,
        "version": SERVICE_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


__all__ = ["app"]
