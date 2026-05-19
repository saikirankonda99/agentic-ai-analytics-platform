from __future__ import annotations

import llm


class _Usage:
    prompt_tokens = 10
    completion_tokens = 5
    total_tokens = 15


class _Message:
    content = "SELECT * FROM Customer LIMIT 50"


class _Choice:
    message = _Message()


class _Response:
    choices = [_Choice()]
    usage = _Usage()


class _Completions:
    def __init__(self, response=None, error: Exception | None = None) -> None:
        self.response = response
        self.error = error
        self.payload = None

    def create(self, **payload):
        self.payload = payload
        if self.error is not None:
            raise self.error
        return self.response


class _Chat:
    def __init__(self, completions: _Completions) -> None:
        self.completions = completions


class _Client:
    def __init__(self, completions: _Completions) -> None:
        self.chat = _Chat(completions)


def test_generate_sql_parses_openai_v1_chat_completion(monkeypatch) -> None:
    completions = _Completions(response=_Response())
    monkeypatch.setattr(llm, "_client", _Client(completions))

    result = llm.generate_sql_with_telemetry("List customers", "CREATE TABLE Customer(id INTEGER)")

    assert result["sql"] == "SELECT * FROM Customer LIMIT 50"
    assert result["telemetry"]["prompt_tokens"] == 10
    assert result["telemetry"]["completion_tokens"] == 5
    assert completions.payload["messages"][0]["role"] == "user"
    assert completions.payload["model"] == llm.DEFAULT_SQL_MODEL


def test_generate_sql_returns_structured_error_telemetry(monkeypatch) -> None:
    completions = _Completions(error=RuntimeError("boom"))
    monkeypatch.setattr(llm, "_client", _Client(completions))
    monkeypatch.setattr(llm, "DEFAULT_OPENAI_MAX_ATTEMPTS", 1)

    result = llm.generate_sql_with_telemetry("List customers", "CREATE TABLE Customer(id INTEGER)")

    assert result["sql"].startswith("ERROR: RuntimeError")
    assert result["telemetry"]["error_type"] == "RuntimeError"
    assert result["telemetry"]["error_message"] == "boom"
    assert result["telemetry"]["error_details"]["operation"] == "chat.completions.create"
