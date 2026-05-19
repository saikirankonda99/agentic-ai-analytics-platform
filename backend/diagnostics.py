from __future__ import annotations

from typing import Any

from backend.connectors import get_connector_registry
from backend.auth_sessions import validate_auth_config
from backend.config import settings, validate_settings
from backend.policies import default_execution_policy
from backend.startup import run_startup_validation
from backend.telemetry import TELEMETRY_SCHEMA_VERSION


def runtime_diagnostics(readiness: dict[str, str] | None = None) -> dict[str, Any]:
    try:
        from llm import validate_openai_runtime

        openai_runtime = validate_openai_runtime()
    except Exception as exc:  # pragma: no cover - defensive endpoint behavior
        openai_runtime = {"available": False, "error_type": type(exc).__name__, "error_message": str(exc)}

    try:
        connector_runtime = get_connector_registry().diagnostics(validate=True)
    except Exception as exc:  # pragma: no cover - defensive endpoint behavior
        connector_runtime = {"available": False, "error_type": type(exc).__name__, "error_message": str(exc)}

    return {
        "service": "agentic-ai-analytics-backend",
        "environment": settings.environment,
        "telemetry_schema_version": TELEMETRY_SCHEMA_VERSION,
        "readiness": readiness or {},
        "runtime": {
            "backend_host": settings.backend_host,
            "backend_port": settings.backend_port,
            "streamlit_port": settings.streamlit_port,
            "workflow_database_url": settings.workflow_database_url,
            "orchestration_queue": settings.orchestration_queue,
            "redis_configured": bool(settings.redis_url),
            "postgres_configured": bool(settings.postgres_url),
            "vector_database_configured": bool(settings.vector_database_url),
        },
        "configuration": validate_settings(settings),
        "auth": validate_auth_config(),
        "startup": run_startup_validation(strict=False, validate_connectors=False),
        "execution_policy": default_execution_policy().as_dict(),
        "connectors": connector_runtime,
        "openai": openai_runtime,
    }
