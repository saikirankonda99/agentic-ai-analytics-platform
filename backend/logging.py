from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from backend.config import settings


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def configure_logging() -> None:
    root_logger = logging.getLogger()
    if root_logger.handlers:
        return

    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root_logger.addHandler(handler)
    root_logger.setLevel(settings.log_level.upper())


def get_logger(name: str) -> logging.Logger:
    configure_logging()
    return logging.getLogger(name)


__all__ = ["JsonFormatter", "configure_logging", "get_logger"]
