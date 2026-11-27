from __future__ import annotations

import json
import logging

import llm
from backend.logging import JsonFormatter
from backend.redaction import redact


def test_provider_errors_do_not_expose_keys_in_telemetry_or_logs(monkeypatch, caplog):
    fake_key = "sk-proj-" + "synthetic-test-credential" * 3
    monkeypatch.setenv("OPENAI_API_KEY", fake_key)
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy-user:proxy-password@example.invalid:8080")
    try:
        raise RuntimeError(f"Authorization failed with key {fake_key}")
    except RuntimeError as cause:
        try:
            raise RuntimeError("Upstream request failed") from cause
        except RuntimeError as exc:
            with caplog.at_level(logging.ERROR):
                payload = llm._log_openai_exception(exc, attempt=1, attempts=1, operation="test")
    combined = json.dumps(payload) + caplog.text
    assert fake_key not in combined
    assert "proxy-password" not in combined
    assert "[REDACTED]" in combined
    assert payload["error_type"] == "RuntimeError"


def test_recursive_redaction_preserves_useful_counts():
    sanitized = redact({"authorization": "private", "token_usage": {"total_tokens": 12},
                        "detail": "postgresql://someone:secret@localhost/app"})
    assert sanitized["authorization"] == "[REDACTED]"
    assert sanitized["token_usage"]["total_tokens"] == 12
    assert "secret" not in sanitized["detail"]


def test_formatter_redacts_exception_without_mutating_the_exception():
    fake_key = "sk-proj-" + "fake-credential" * 3
    exc = RuntimeError(fake_key)
    record = logging.LogRecord("test", logging.ERROR, __file__, 1, "failed", (), (type(exc), exc, None))
    rendered = JsonFormatter().format(record)
    assert fake_key not in rendered
    assert str(exc) == fake_key
