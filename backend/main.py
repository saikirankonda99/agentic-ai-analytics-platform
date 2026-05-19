from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.config import settings
from backend.logging import configure_logging, get_logger
from backend.middleware import RequestContextMiddleware
from backend.routes import SERVICE_VERSION, router
from backend.startup import run_startup_validation

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    app.state.settings = settings
    app.state.startup_validation = run_startup_validation()
    logger.info("backend_startup diagnostics=%s", app.state.startup_validation.get("summary", {}))
    yield
    logger.info("backend_shutdown")


app = FastAPI(
    title="Agentic AI Analytics Backend",
    version=SERVICE_VERSION,
    lifespan=lifespan,
)
app.add_middleware(RequestContextMiddleware)
app.include_router(router)


__all__ = ["app"]
