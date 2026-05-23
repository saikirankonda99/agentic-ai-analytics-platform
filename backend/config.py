from __future__ import annotations

from dataclasses import dataclass
from os import getenv
from typing import Any


DEFAULT_PLATFORM_DATABASE_URL = "sqlite:///data/platform_persistence.db"
DEFAULT_WORKFLOW_DATABASE_URL = "sqlite:///data/workflow_runtime.db"


@dataclass(frozen=True)
class AppSettings:
    environment: str = "development"
    log_level: str = "INFO"
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    streamlit_port: int = 8501
    workflow_database_url: str = DEFAULT_WORKFLOW_DATABASE_URL
    database_url: str = DEFAULT_PLATFORM_DATABASE_URL
    workflow_database_source: str = "default"
    redis_url: str | None = None
    postgres_url: str | None = None
    vector_database_url: str | None = None
    orchestration_queue: str = "orchestration.workflows"
    websocket_channel_prefix: str = "workflow"

    @property
    def sqlite_workflow_path(self) -> str:
        prefix = "sqlite:///"
        if self.workflow_database_url.startswith(prefix):
            return self.workflow_database_url.removeprefix(prefix)
        return "data/workflow_runtime.db"

    @property
    def database_backend(self) -> str:
        if self.database_url.startswith("postgresql://") or self.database_url.startswith("postgres://"):
            return "postgresql"
        return "sqlite"

    @property
    def workflow_database_backend(self) -> str:
        if self.workflow_database_url.startswith("postgresql://") or self.workflow_database_url.startswith("postgres://"):
            return "postgresql"
        return "sqlite"


def get_settings() -> AppSettings:
    database_url = getenv("DATABASE_URL", getenv("PLATFORM_DATABASE_URL", DEFAULT_PLATFORM_DATABASE_URL))
    workflow_database_url = getenv("WORKFLOW_DATABASE_URL")
    workflow_database_source = "WORKFLOW_DATABASE_URL"
    if not workflow_database_url:
        workflow_database_url = getenv("DATABASE_URL") or DEFAULT_WORKFLOW_DATABASE_URL
        workflow_database_source = "DATABASE_URL" if getenv("DATABASE_URL") else "default"

    return AppSettings(
        environment=getenv("APP_ENV", "development"),
        log_level=getenv("LOG_LEVEL", "INFO"),
        backend_host=getenv("BACKEND_HOST", "0.0.0.0"),
        backend_port=int(getenv("BACKEND_PORT", "8000")),
        streamlit_port=int(getenv("STREAMLIT_SERVER_PORT", "8501")),
        workflow_database_url=workflow_database_url,
        database_url=database_url,
        workflow_database_source=workflow_database_source,
        redis_url=getenv("REDIS_URL"),
        postgres_url=getenv("POSTGRES_URL"),
        vector_database_url=getenv("VECTOR_DATABASE_URL"),
        orchestration_queue=getenv("ORCHESTRATION_QUEUE", "orchestration.workflows"),
        websocket_channel_prefix=getenv("WEBSOCKET_CHANNEL_PREFIX", "workflow"),
    )


def validate_settings(config: AppSettings | None = None) -> dict[str, Any]:
    config = config or settings
    warnings = []
    errors = []
    if config.workflow_database_backend == "postgresql" and not config.workflow_database_url:
        errors.append("WORKFLOW_DATABASE_URL is required for PostgreSQL workflow persistence.")
    if config.database_backend == "postgresql" and not config.database_url:
        errors.append("DATABASE_URL is required for PostgreSQL platform persistence.")
    if config.environment == "production" and config.workflow_database_source == "default":
        errors.append("Production deployments must configure WORKFLOW_DATABASE_URL explicitly.")
    if (
        config.environment == "production"
        and config.database_backend == "postgresql"
        and config.workflow_database_backend == "sqlite"
    ):
        errors.append("Production PostgreSQL platform persistence must not run workflow persistence on SQLite.")
    if config.workflow_database_source == "DATABASE_URL":
        warnings.append("WORKFLOW_DATABASE_URL is not set; workflow persistence is using DATABASE_URL compatibility fallback.")
    if config.workflow_database_source == "WORKFLOW_DATABASE_URL" and config.workflow_database_url != config.database_url:
        warnings.append("DATABASE_URL and WORKFLOW_DATABASE_URL are configured separately; verify this is intentional.")
    if (
        config.database_backend != config.workflow_database_backend
        and not (
            config.database_backend == "sqlite"
            and config.workflow_database_backend == "sqlite"
        )
    ):
        warnings.append("Platform and workflow persistence use different database backends.")
    if config.environment == "production" and not config.redis_url:
        warnings.append("Production orchestration should configure REDIS_URL or another durable worker backend.")
    return {
        "environment": config.environment,
        "valid": not warnings and not errors,
        "warnings": warnings,
        "errors": errors,
        "workflow_database_url": _redact_database_url(config.workflow_database_url),
        "workflow_database_source": config.workflow_database_source,
        "workflow_database_backend": config.workflow_database_backend,
        "database_url": _redact_database_url(config.database_url),
        "database_backend": config.database_backend,
        "queue": config.orchestration_queue,
    }


settings = get_settings()


def _redact_database_url(database_url: str) -> str:
    if "@" not in database_url or "://" not in database_url:
        return database_url
    scheme, rest = database_url.split("://", 1)
    return f"{scheme}://***@{rest.split('@', 1)[1]}"


__all__ = [
    "AppSettings",
    "DEFAULT_PLATFORM_DATABASE_URL",
    "DEFAULT_WORKFLOW_DATABASE_URL",
    "get_settings",
    "settings",
    "validate_settings",
]
