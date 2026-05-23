from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from typing import Any

from backend.auth_sessions import validate_auth_config
from backend.config import settings, validate_settings
from backend.connectors import get_connector_registry
from backend.logging import get_logger
from backend.persistence import validate_platform_database
from backend.storage import validate_workflow_storage
from backend.telemetry import TELEMETRY_SCHEMA_VERSION, validate_telemetry_payload

logger = get_logger(__name__)


@dataclass(frozen=True)
class StartupCheck:
    name: str
    status: str
    message: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def run_startup_validation(*, strict: bool | None = None, validate_connectors: bool = True) -> dict[str, Any]:
    strict = _strict_startup_enabled() if strict is None else strict
    checks = [
        _environment_check(),
        _openai_check(),
        _connector_check(validate_connectors=validate_connectors),
        _database_check(),
        _workflow_database_check(),
        _auth_check(),
        _telemetry_check(),
        _orchestration_check(),
    ]
    invalid = [check for check in checks if check.status == "error"]
    degraded = [check for check in checks if check.status == "warning"]
    status = "error" if invalid else "degraded" if degraded else "ok"
    payload = {
        "status": status,
        "strict": strict,
        "checks": [check.as_dict() for check in checks],
        "summary": {
            "ok": len([check for check in checks if check.status == "ok"]),
            "warning": len(degraded),
            "error": len(invalid),
        },
    }
    logger.info("startup_validation_completed status=%s strict=%s summary=%s", status, strict, payload["summary"])
    if strict and invalid:
        raise RuntimeError(f"Startup validation failed: {[check.name for check in invalid]}")
    return payload


def _environment_check() -> StartupCheck:
    config = validate_settings(settings)
    status = "error" if config.get("errors") else "ok" if config.get("valid") else "warning"
    return StartupCheck(
        name="environment",
        status=status,
        message=(
            "Environment configuration validated."
            if status == "ok"
            else "Environment configuration has errors."
            if status == "error"
            else "Environment configuration has warnings."
        ),
        metadata=config,
    )


def _openai_check() -> StartupCheck:
    try:
        from llm import validate_openai_runtime

        runtime = validate_openai_runtime()
    except Exception as exc:  # pragma: no cover - defensive startup boundary
        return StartupCheck("openai", "error", f"OpenAI runtime validation failed: {type(exc).__name__}: {exc}")

    status = "ok" if runtime.get("api_key_configured") else "warning"
    message = "OpenAI runtime configured." if status == "ok" else "OPENAI_API_KEY is not configured; model calls will degrade."
    return StartupCheck("openai", status, message, _redact_openai_runtime(runtime))


def _connector_check(*, validate_connectors: bool) -> StartupCheck:
    try:
        diagnostics = get_connector_registry().diagnostics(validate=validate_connectors)
    except Exception as exc:
        return StartupCheck("connectors", "error", f"Connector diagnostics failed: {type(exc).__name__}: {exc}")

    health = diagnostics.get("health", {})
    required_sqlite = health.get("sqlite", {}).get("status") if validate_connectors else "healthy"
    status = "ok" if required_sqlite in {"healthy", None} else "error"
    return StartupCheck(
        name="connectors",
        status=status,
        message="Connector registry validated." if status == "ok" else "Required SQLite connector is unavailable.",
        metadata=diagnostics,
    )


def _auth_check() -> StartupCheck:
    diagnostics = validate_auth_config()
    status = "ok" if diagnostics.get("valid") else "warning"
    return StartupCheck(
        name="auth",
        status=status,
        message="Authentication configuration validated." if status == "ok" else "Authentication configuration has warnings.",
        metadata=diagnostics,
    )


def _database_check() -> StartupCheck:
    diagnostics = validate_platform_database(settings.database_url)
    status = "ok" if diagnostics.get("status") == "ok" else "warning"
    return StartupCheck(
        name="database",
        status=status,
        message="Platform persistence database validated." if status == "ok" else "Platform persistence is degraded; file fallback may be used.",
        metadata=diagnostics,
    )


def _workflow_database_check() -> StartupCheck:
    diagnostics = validate_workflow_storage()
    status = "ok" if diagnostics.get("status") == "ok" else "error"
    logger.info(
        "workflow_persistence_selected backend=%s source=%s database_url=%s",
        diagnostics.get("backend"),
        diagnostics.get("source"),
        diagnostics.get("database_url"),
    )
    return StartupCheck(
        name="workflow_database",
        status=status,
        message=(
            "Workflow persistence database validated."
            if status == "ok"
            else "Workflow persistence database is unavailable."
        ),
        metadata=diagnostics,
    )


def _telemetry_check() -> StartupCheck:
    telemetry = validate_telemetry_payload({"steps": []})
    status = "ok" if telemetry.get("schema_version") == TELEMETRY_SCHEMA_VERSION else "error"
    return StartupCheck(
        name="telemetry",
        status=status,
        message="Telemetry schema initialized." if status == "ok" else "Telemetry schema validation failed.",
        metadata={"schema_version": telemetry.get("schema_version"), "correlation_id_present": bool(telemetry.get("correlation_id"))},
    )


def _orchestration_check() -> StartupCheck:
    try:
        from graph.workflow import workflow
        from backend.runtime import orchestration_runtime

        initialized = workflow is not None or orchestration_runtime is not None
    except Exception as exc:
        return StartupCheck("orchestration", "error", f"Orchestration initialization failed: {type(exc).__name__}: {exc}")
    return StartupCheck(
        name="orchestration",
        status="ok" if initialized else "warning",
        message="Orchestration runtime initialized." if initialized else "Orchestration runtime is using degraded linear mode.",
        metadata={"langgraph_compiled": workflow is not None},
    )


def _strict_startup_enabled() -> bool:
    return os.getenv("STARTUP_VALIDATION_STRICT", "false").strip().lower() in {"1", "true", "yes", "on"}


def _redact_openai_runtime(runtime: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in runtime.items()
        if key not in {"proxy_env"}
    } | {"proxy_env_keys": sorted((runtime.get("proxy_env") or {}).keys())}


if __name__ == "__main__":
    run_startup_validation()
