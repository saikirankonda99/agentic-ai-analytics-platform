from __future__ import annotations

from dataclasses import dataclass
from os import getenv
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from dotenv import load_dotenv


# Load local configuration before constructing the process settings snapshot.
# Explicit host/container environment variables retain precedence.
load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)


DEFAULT_PLATFORM_DATABASE_URL = "sqlite:///data/platform_persistence.db"
DEFAULT_WORKFLOW_DATABASE_URL = "sqlite:///data/workflow_runtime.db"


def database_backend_for_url(database_url: str) -> str:
    if database_url.startswith("sqlite:///") and database_url.removeprefix("sqlite:///").strip():
        if database_url.removeprefix("sqlite:///") == ":memory:":
            raise ValueError("Durable storage requires a SQLite file, not an in-memory database.")
        return "sqlite"
    if database_url.startswith(("postgresql://", "postgres://")) and urlsplit(database_url).path.strip("/"):
        return "postgresql"
    raise ValueError("Storage requires an explicit sqlite:///file or postgresql://host/database URL.")


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

    def __post_init__(self) -> None:
        database_backend_for_url(self.database_url)
        database_backend_for_url(self.workflow_database_url)

    @property
    def sqlite_workflow_path(self) -> str:
        prefix = "sqlite:///"
        if self.workflow_database_url.startswith(prefix):
            return self.workflow_database_url.removeprefix(prefix)
        return "data/workflow_runtime.db"

    @property
    def database_backend(self) -> str:
        return database_backend_for_url(self.database_url)

    @property
    def workflow_database_backend(self) -> str:
        return database_backend_for_url(self.workflow_database_url)


def get_settings() -> AppSettings:
    database_url = getenv("DATABASE_URL", getenv("PLATFORM_DATABASE_URL", DEFAULT_PLATFORM_DATABASE_URL))
    workflow_database_url = getenv("WORKFLOW_DATABASE_URL")
    workflow_database_source = "WORKFLOW_DATABASE_URL"
    if not workflow_database_url:
        workflow_database_url = getenv("DATABASE_URL") or DEFAULT_WORKFLOW_DATABASE_URL
        workflow_database_source = "DATABASE_URL" if getenv("DATABASE_URL") else "default"

    return AppSettings(
        environment=getenv("APP_ENV", "development").strip().lower(),
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
    if config.environment == "production" and getenv("ANALYTICS_WORKER_MODE", "external") != "external":
        errors.append("Production analytics requires ANALYTICS_WORKER_MODE=external and a supervised worker process.")
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
    parsed = urlsplit(database_url)
    netloc = parsed.netloc.rsplit("@", 1)[-1]
    return urlunsplit((parsed.scheme, "***@" + netloc, parsed.path, "", ""))


__all__ = [
    "AppSettings",
    "DEFAULT_PLATFORM_DATABASE_URL",
    "DEFAULT_WORKFLOW_DATABASE_URL",
    "get_settings",
    "settings",
    "validate_settings",
]
