from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from backend.config import settings


class EventBus(Protocol):
    def publish(self, channel: str, payload: str) -> None:
        """Publish a serialized event payload."""


class InMemoryEventBus:
    def __init__(self) -> None:
        self.messages: list[tuple[str, str]] = []

    def publish(self, channel: str, payload: str) -> None:
        self.messages.append((channel, payload))


@dataclass
class RedisEventBus:
    redis_url: str

    def publish(self, channel: str, payload: str) -> None:
        import redis

        client = redis.Redis.from_url(self.redis_url)
        client.publish(channel, payload)


def build_event_bus() -> EventBus:
    if settings.redis_url:
        return RedisEventBus(settings.redis_url)
    return InMemoryEventBus()


event_bus = build_event_bus()


__all__ = ["EventBus", "InMemoryEventBus", "RedisEventBus", "build_event_bus", "event_bus"]
