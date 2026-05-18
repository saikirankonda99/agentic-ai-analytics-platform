from __future__ import annotations

from dataclasses import dataclass
from os import getenv


@dataclass(frozen=True)
class AppSettings:
    environment: str = "development"
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    streamlit_port: int = 8501
    workflow_database_url: str = "sqlite:///data/workflow_runtime.db"
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


def get_settings() -> AppSettings:
    return AppSettings(
        environment=getenv("APP_ENV", "development"),
        backend_host=getenv("BACKEND_HOST", "0.0.0.0"),
        backend_port=int(getenv("BACKEND_PORT", "8000")),
        streamlit_port=int(getenv("STREAMLIT_SERVER_PORT", "8501")),
        workflow_database_url=getenv("WORKFLOW_DATABASE_URL", "sqlite:///data/workflow_runtime.db"),
        redis_url=getenv("REDIS_URL"),
        postgres_url=getenv("POSTGRES_URL"),
        vector_database_url=getenv("VECTOR_DATABASE_URL"),
        orchestration_queue=getenv("ORCHESTRATION_QUEUE", "orchestration.workflows"),
        websocket_channel_prefix=getenv("WEBSOCKET_CHANNEL_PREFIX", "workflow"),
    )


settings = get_settings()


__all__ = ["AppSettings", "get_settings", "settings"]
