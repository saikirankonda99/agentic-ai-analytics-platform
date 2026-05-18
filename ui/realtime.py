from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RealtimeSyncConfig:
    backend_http_url: str = "http://localhost:8000"
    backend_ws_url: str = "ws://localhost:8000"
    enabled: bool = False


def workflow_websocket_url(workflow_id: str, config: RealtimeSyncConfig | None = None) -> str:
    realtime_config = config or RealtimeSyncConfig()
    return f"{realtime_config.backend_ws_url}/workflow/{workflow_id}/ws"


def workflow_sse_url(workflow_id: str, config: RealtimeSyncConfig | None = None) -> str:
    realtime_config = config or RealtimeSyncConfig()
    return f"{realtime_config.backend_http_url}/workflow/{workflow_id}/stream"


__all__ = ["RealtimeSyncConfig", "workflow_sse_url", "workflow_websocket_url"]
