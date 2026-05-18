from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


class RelationalStore(Protocol):
    def execute(self, sql: str) -> tuple[list[str], list[Any]]:
        """Execute read-only analytical SQL."""


class CacheStore(Protocol):
    def get(self, key: str) -> Any:
        """Read cached workflow state."""

    def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        """Persist cached workflow state."""


class VectorMemoryStore(Protocol):
    def search(self, query: str, top_k: int = 3) -> list[dict[str, Any]]:
        """Retrieve semantically similar workspace memories."""


class BackgroundWorker(Protocol):
    def enqueue(self, task_name: str, payload: dict[str, Any]) -> str:
        """Queue a task for asynchronous execution."""


@dataclass(frozen=True)
class BackendConfig:
    relational_backend: str = "sqlite"
    cache_backend: str = "in_memory"
    vector_backend: str = "chromadb"
    worker_backend: str = "inline"


class InMemoryCache:
    def __init__(self) -> None:
        self._values: dict[str, Any] = {}

    def get(self, key: str) -> Any:
        return self._values.get(key)

    def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        self._values[key] = value


class InlineWorker:
    def enqueue(self, task_name: str, payload: dict[str, Any]) -> str:
        return f"inline:{task_name}:{payload.get('run_id', 'default')}"
