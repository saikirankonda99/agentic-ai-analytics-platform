from __future__ import annotations

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI

from backend.config import settings
from backend.routes import SERVICE_VERSION, router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.settings = settings
    yield


app = FastAPI(
    title="Agentic AI Analytics Backend",
    version=SERVICE_VERSION,
    lifespan=lifespan,
)
app.include_router(router)


__all__ = ["app"]
