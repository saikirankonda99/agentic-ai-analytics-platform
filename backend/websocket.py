from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from json import dumps

from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect

from backend.config import settings
from backend.messaging import EventBus, event_bus
from backend.models import DEFAULT_ORGANIZATION_ID, DEFAULT_WORKSPACE_ID, WorkflowStreamUpdate


@dataclass(frozen=True)
class WebSocketChannel:
    organization_id: str
    workspace_id: str
    workflow_id: str


class WebSocketConnectionManager:
    def __init__(self, bus: EventBus = event_bus) -> None:
        self.bus = bus
        self._connections: dict[WebSocketChannel, set[WebSocket]] = defaultdict(set)

    async def connect(self, websocket: WebSocket, channel: WebSocketChannel) -> None:
        await websocket.accept()
        self._connections[channel].add(websocket)

    def disconnect(self, websocket: WebSocket, channel: WebSocketChannel) -> None:
        connections = self._connections.get(channel)
        if connections is None:
            return

        connections.discard(websocket)
        if not connections:
            self._connections.pop(channel, None)

    async def broadcast(self, channel: WebSocketChannel, update: WorkflowStreamUpdate) -> None:
        self.bus.publish(_channel_name(channel), _serialize_update(update))
        stale_connections: list[WebSocket] = []
        for websocket in tuple(self._connections.get(channel, ())):
            try:
                await websocket.send_text(_serialize_update(update))
            except WebSocketDisconnect:
                stale_connections.append(websocket)
            except RuntimeError:
                stale_connections.append(websocket)

        for websocket in stale_connections:
            self.disconnect(websocket, channel)


def workflow_channel(
    workflow_id: str,
    workspace_id: str = DEFAULT_WORKSPACE_ID,
    organization_id: str = DEFAULT_ORGANIZATION_ID,
) -> WebSocketChannel:
    return WebSocketChannel(
        organization_id=organization_id,
        workspace_id=workspace_id,
        workflow_id=workflow_id,
    )


def _serialize_update(update: WorkflowStreamUpdate) -> str:
    return dumps(
        {
            "timestamp": update.timestamp,
            "update_type": update.update_type,
            "message": update.message,
            "payload": update.payload,
        }
    )


def _channel_name(channel: WebSocketChannel) -> str:
    return (
        f"{settings.websocket_channel_prefix}:"
        f"{channel.organization_id}:{channel.workspace_id}:{channel.workflow_id}"
    )


websocket_manager = WebSocketConnectionManager()


__all__ = [
    "WebSocketChannel",
    "WebSocketConnectionManager",
    "websocket_manager",
    "workflow_channel",
]
