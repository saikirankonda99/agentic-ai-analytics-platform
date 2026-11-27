from __future__ import annotations

from typing import Any

from backend.connectors import get_connector_registry
from backend.auth_sessions import validate_auth_config
from backend.config import settings, validate_settings
from backend.policies import default_execution_policy
from backend.retry import retry_diagnostics
from backend.telemetry import TELEMETRY_SCHEMA_VERSION


def runtime_diagnostics(
    readiness: dict[str, str] | None = None, *, organization_id: str | None = None,
    workspace_id: str | None = None,
) -> dict[str, Any]:
    """Workspace diagnostics must not expose another customer's connectors or host secrets."""
    if bool(organization_id) != bool(workspace_id):
        raise PermissionError("Both organization and workspace are required for diagnostics.")
    try:
        from llm import validate_openai_runtime
        raw_openai = validate_openai_runtime()
        openai_runtime = {key: raw_openai[key] for key in (
            "api_key_configured", "timeout_seconds", "max_attempts", "retry_policy", "fallback_model"
        ) if key in raw_openai}
    except Exception as exc:
        openai_runtime = {"available": False, "error_type": type(exc).__name__}
    # Unscoped local diagnostics may inspect only the bundled public example.
    scope = {"organization_id": organization_id or "organization:example-diagnostics",
             "workspace_id": workspace_id or "workspace:example-diagnostics"}
    try:
        connector_runtime = get_connector_registry().diagnostics_for_workspace(**scope, validate=True)
    except Exception as exc:
        connector_runtime = {"available": False, "error_type": type(exc).__name__}
    configuration = validate_settings(settings)
    auth = validate_auth_config()
    return {
        "service": "agentic-ai-analytics-backend",
        "environment": settings.environment,
        "telemetry_schema_version": TELEMETRY_SCHEMA_VERSION,
        "readiness": readiness or {},
        "runtime": {
            "workflow_database_backend": configuration["workflow_database_backend"],
            "worker_queue": "durable workflow database",
        },
        "configuration": {key: configuration[key] for key in ("environment", "valid", "warnings", "errors")},
        "auth": {key: auth[key] for key in ("valid", "session_storage", "session_ttl_hours", "supports_password_hashes")},
        "startup": {
            "scope": "configuration_and_authentication",
            "configuration_valid": not configuration["errors"],
            "auth_valid": auth["valid"],
            "summary": {
                "error": int(bool(configuration["errors"])) + int(not auth["valid"]),
                "warning": int(bool(configuration["warnings"]) and not configuration["errors"])
                + int(bool(auth["warnings"]) and auth["valid"]),
                "ok": int(not configuration["errors"] and not configuration["warnings"])
                + int(auth["valid"] and not auth["warnings"]),
            },
        },
        "execution_policy": default_execution_policy().as_dict(),
        "retry_policy": retry_diagnostics(),
        "connectors": connector_runtime,
        "openai": openai_runtime,
    }
