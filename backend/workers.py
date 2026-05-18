from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol
from uuid import uuid4

from backend.config import settings


class DistributedWorkerQueue(Protocol):
    def enqueue(self, task_name: str, payload: dict[str, Any]) -> str:
        """Submit work to an orchestration queue."""


class InlineWorkerQueue:
    def enqueue(self, task_name: str, payload: dict[str, Any]) -> str:
        return f"inline:{task_name}:{payload.get('workflow_id', 'default')}"


@dataclass
class RedisWorkerQueue:
    redis_url: str
    queue_name: str = settings.orchestration_queue

    def enqueue(self, task_name: str, payload: dict[str, Any]) -> str:
        import redis

        job_id = f"job:{uuid4()}"
        client = redis.Redis.from_url(self.redis_url)
        client.xadd(
            self.queue_name,
            {"job_id": job_id, "task_name": task_name, "payload": repr(payload)},
        )
        return job_id


def build_worker_queue() -> DistributedWorkerQueue:
    if settings.redis_url:
        return RedisWorkerQueue(settings.redis_url)
    return InlineWorkerQueue()


worker_queue = build_worker_queue()


__all__ = [
    "DistributedWorkerQueue",
    "InlineWorkerQueue",
    "RedisWorkerQueue",
    "build_worker_queue",
    "worker_queue",
]
