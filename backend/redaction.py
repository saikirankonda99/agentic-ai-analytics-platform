"""Remove credential material before diagnostic text reaches logs or clients."""
from __future__ import annotations

import os
import re
from typing import Any


_KEY_PATTERN = re.compile(r"\bsk-[A-Za-z0-9_-]{8,}")
_BEARER_PATTERN = re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._~+/-]{8,}=*")
_URL_PASSWORD = re.compile(r"([a-zA-Z][a-zA-Z0-9+.-]*://)[^\s/@:]+:[^\s/@]+@")
_SECRET_FIELDS = {"api_key", "apikey", "authorization", "password", "access_token", "refresh_token", "session_token"}


def redact_text(value: str) -> str:
    text = str(value)
    for name, secret in os.environ.items():
        if (name.endswith(("API_KEY", "PASSWORD", "TOKEN", "SECRET")) or name in {"AUTH_USERS"}) and len(secret) >= 8:
            text = text.replace(secret, "[REDACTED]")
    text = _KEY_PATTERN.sub("[REDACTED]", text)
    text = _BEARER_PATTERN.sub(r"\1[REDACTED]", text)
    return _URL_PASSWORD.sub(r"\1[REDACTED]@", text)


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "[REDACTED]" if str(key).lower() in _SECRET_FIELDS else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [redact(item) for item in value]
    return redact_text(value) if isinstance(value, str) else value
