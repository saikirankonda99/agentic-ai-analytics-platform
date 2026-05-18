from __future__ import annotations

from fastapi import FastAPI

from backend.routes import SERVICE_VERSION, router

app = FastAPI(
    title="Agentic AI Analytics Backend",
    version=SERVICE_VERSION,
)
app.include_router(router)


__all__ = ["app"]
