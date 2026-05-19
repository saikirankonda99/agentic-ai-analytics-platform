from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any, Callable

import httpx
import streamlit as st
from dotenv import load_dotenv
from openai import APIConnectionError, APIError, APIStatusError, APITimeoutError, OpenAI

from graph.cost_tracker import estimate_cost

try:
    from backend.logging import get_logger

    logger = get_logger(__name__)
except Exception:  # pragma: no cover - supports isolated imports in tooling
    import logging

    logger = logging.getLogger(__name__)


DOTENV_PATH = Path(__file__).resolve().parent / ".env"
DOTENV_LOADED = load_dotenv(DOTENV_PATH)
DEFAULT_SQL_MODEL = "gpt-4o-mini"
DEFAULT_FALLBACK_MODEL = os.getenv("OPENAI_FALLBACK_MODEL", "").strip()
DEFAULT_OPENAI_TIMEOUT_SECONDS = float(os.getenv("OPENAI_TIMEOUT_SECONDS", "30"))
DEFAULT_OPENAI_MAX_ATTEMPTS = max(int(os.getenv("OPENAI_MAX_ATTEMPTS", "2")), 1)
OPENAI_TRUST_ENV = os.getenv("OPENAI_TRUST_ENV", "false").lower() in {"1", "true", "yes"}

TokenCallback = Callable[[str, str], None]


def get_openai_api_key() -> str | None:
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        return api_key

    try:
        return st.secrets["OPENAI_API_KEY"]
    except Exception:
        return None


def _configured_proxy_env() -> dict[str, str]:
    proxy_keys = ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY")
    return {key: value for key in proxy_keys if (value := os.getenv(key))}


def validate_openai_runtime() -> dict[str, Any]:
    return {
        "dotenv_path": str(DOTENV_PATH),
        "dotenv_loaded": DOTENV_LOADED,
        "api_key_configured": bool(get_openai_api_key()),
        "timeout_seconds": DEFAULT_OPENAI_TIMEOUT_SECONDS,
        "max_attempts": DEFAULT_OPENAI_MAX_ATTEMPTS,
        "fallback_model": DEFAULT_FALLBACK_MODEL or None,
        "trust_env": OPENAI_TRUST_ENV,
        "proxy_env": _configured_proxy_env(),
    }


def build_openai_client() -> OpenAI:
    api_key = get_openai_api_key()
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not configured. Add it to the environment, Streamlit secrets, or the project .env file."
        )

    timeout = httpx.Timeout(DEFAULT_OPENAI_TIMEOUT_SECONDS)
    return OpenAI(
        api_key=api_key,
        timeout=timeout,
        max_retries=0,
        http_client=httpx.Client(timeout=timeout, trust_env=OPENAI_TRUST_ENV),
    )


_client: OpenAI | None = None


def get_openai_client() -> OpenAI:
    global _client
    if _client is None:
        _client = build_openai_client()
        logger.info("openai_client_initialized diagnostics=%s", validate_openai_runtime())
    return _client


def _exception_chain(exc: BaseException) -> list[dict[str, str]]:
    chain = []
    current: BaseException | None = exc
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        chain.append({"type": type(current).__name__, "message": str(current), "repr": repr(current)})
        current = current.__cause__ or current.__context__
    return chain


def _openai_exception_payload(exc: BaseException, *, attempt: int, attempts: int, operation: str) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "operation": operation,
        "attempt": attempt,
        "max_attempts": attempts,
        "error_type": type(exc).__name__,
        "error_message": str(exc),
        "exception_chain": _exception_chain(exc),
        "runtime": validate_openai_runtime(),
    }
    if isinstance(exc, APIStatusError):
        payload.update({"status_code": exc.status_code, "request_id": exc.request_id, "response_body": exc.body})
    elif isinstance(exc, APIError):
        payload.update(
            {
                "request_id": getattr(exc, "request_id", None),
                "status_code": getattr(exc, "status_code", None),
                "code": getattr(exc, "code", None),
                "param": getattr(exc, "param", None),
                "body": getattr(exc, "body", None),
            }
        )
    return payload


def _log_openai_exception(exc: BaseException, *, attempt: int, attempts: int, operation: str) -> dict[str, Any]:
    payload = _openai_exception_payload(exc, attempt=attempt, attempts=attempts, operation=operation)
    logger.error(
        "openai_request_failed operation=%s attempt=%s/%s error_type=%s error_message=%s details=%s",
        operation,
        attempt,
        attempts,
        payload["error_type"],
        payload["error_message"],
        payload,
        exc_info=True,
    )
    return payload


def _telemetry(
    model: str,
    *,
    started: float,
    usage: Any = None,
    error: dict[str, Any] | None = None,
) -> dict[str, Any]:
    prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
    completion_tokens = getattr(usage, "completion_tokens", 0) or 0
    total_tokens = getattr(usage, "total_tokens", 0) or (prompt_tokens + completion_tokens)
    usage_available = usage is not None
    telemetry = {
        "model": model,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "cost_usd": estimate_cost(model, prompt_tokens, completion_tokens) if usage_available else 0.0,
        "latency_ms": int((time.perf_counter() - started) * 1000),
        "usage_available": usage_available,
        "openai_timeout_seconds": DEFAULT_OPENAI_TIMEOUT_SECONDS,
        "openai_max_attempts": DEFAULT_OPENAI_MAX_ATTEMPTS,
    }
    if error:
        telemetry.update(
            {
                "error_type": error.get("error_type"),
                "error_message": error.get("error_message"),
                "error_attempt": error.get("attempt"),
                "error_max_attempts": error.get("max_attempts"),
                "error_details": error,
            }
        )
    return telemetry


def _chat_completion_payload(prompt: str, model: str, temperature: float, *, stream: bool = False) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
    }
    if stream:
        payload.update({"stream": True, "stream_options": {"include_usage": True}})
    return payload


def _request_error_text(error: dict[str, Any]) -> str:
    chain = error.get("exception_chain") or []
    root = chain[-1] if chain else {}
    root_text = f" Root cause: {root.get('type')}: {root.get('message')}" if root else ""
    return f"ERROR: {error.get('error_type', 'OpenAIError')}: {error.get('error_message', 'Request failed')}.{root_text}"


def _model_candidates(model: str) -> list[str]:
    candidates = [model]
    if DEFAULT_FALLBACK_MODEL and DEFAULT_FALLBACK_MODEL not in candidates:
        candidates.append(DEFAULT_FALLBACK_MODEL)
    return candidates


def generate_sql_with_telemetry(question: str, schema: str, model: str = DEFAULT_SQL_MODEL) -> dict[str, Any]:
    prompt = f"""
You are an expert SQL generator.

Database schema:
{schema}

Rules:
- Return ONLY raw SQL
- Do NOT use markdown (no ```sql)
- Do NOT explain anything
- Use correct column names
- Limit results to 50

User question:
{question}
"""

    started = time.perf_counter()
    last_error = None

    candidates = _model_candidates(model)
    for candidate_model in candidates:
        for attempt in range(1, DEFAULT_OPENAI_MAX_ATTEMPTS + 1):
            try:
                response = get_openai_client().chat.completions.create(
                    **_chat_completion_payload(prompt, candidate_model, 0)
                )
                content = response.choices[0].message.content or ""
                telemetry = _telemetry(candidate_model, started=started, usage=getattr(response, "usage", None))
                if candidate_model != model:
                    telemetry["fallback_model"] = candidate_model
                    telemetry["primary_model"] = model
                return {
                    "sql": content.strip().replace("```sql", "").replace("```", ""),
                    "telemetry": telemetry,
                }
            except (APIConnectionError, APITimeoutError, APIStatusError, APIError, httpx.HTTPError, RuntimeError) as exc:
                last_error = _log_openai_exception(
                    exc,
                    attempt=attempt,
                    attempts=DEFAULT_OPENAI_MAX_ATTEMPTS,
                    operation="chat.completions.create",
                )
                if attempt < DEFAULT_OPENAI_MAX_ATTEMPTS:
                    time.sleep(0.4 * attempt)
                    continue
                break

        if candidate_model != candidates[-1]:
            logger.warning(
                "openai_primary_model_failed attempting_fallback primary_model=%s fallback_model=%s error_type=%s",
                model,
                candidates[-1],
                (last_error or {}).get("error_type"),
            )

    if last_error and len(candidates) > 1:
        last_error["fallback_model"] = candidates[-1]
        last_error["primary_model"] = model
    return {
        "sql": _request_error_text(last_error or {}),
        "telemetry": _telemetry(model, started=started, error=last_error),
    }


def generate_sql(question: str, schema: str) -> str:
    return generate_sql_with_telemetry(question, schema)["sql"]


def stream_sql_with_telemetry(
    question: str,
    schema: str,
    model: str = DEFAULT_SQL_MODEL,
    token_callback: TokenCallback | None = None,
) -> dict[str, Any]:
    prompt = f"""
You are an expert SQL generator.

Database schema:
{schema}

Rules:
- Return ONLY raw SQL
- Do NOT use markdown (no ```sql)
- Do NOT explain anything
- Use correct column names
- Limit results to 50

User question:
{question}
"""

    return stream_text_with_telemetry(
        prompt,
        model=model,
        temperature=0,
        token_callback=token_callback,
        cleanup_sql=True,
    )


def stream_text_with_telemetry(
    prompt: str,
    model: str = DEFAULT_SQL_MODEL,
    temperature: float = 0,
    token_callback: TokenCallback | None = None,
    cleanup_sql: bool = False,
) -> dict[str, Any]:
    started = time.perf_counter()
    last_error = None

    for candidate_model in _model_candidates(model):
        for attempt in range(1, DEFAULT_OPENAI_MAX_ATTEMPTS + 1):
            content_parts = []
            try:
                try:
                    stream = get_openai_client().chat.completions.create(
                        **_chat_completion_payload(prompt, candidate_model, temperature, stream=True)
                    )
                except TypeError:
                    fallback_payload = {
                        key: value
                        for key, value in _chat_completion_payload(prompt, candidate_model, temperature, stream=True).items()
                        if key != "stream_options"
                    }
                    stream = get_openai_client().chat.completions.create(**fallback_payload)

                usage = None
                for chunk in stream:
                    usage = getattr(chunk, "usage", None) or usage
                    choices = getattr(chunk, "choices", None) or []
                    if not choices:
                        continue
                    delta = getattr(choices[0], "delta", None)
                    token = getattr(delta, "content", None) if delta is not None else None
                    if not token:
                        continue
                    content_parts.append(token)
                    if token_callback is not None:
                        token_callback(token, "".join(content_parts))

                text = "".join(content_parts).strip()
                if cleanup_sql:
                    text = text.replace("```sql", "").replace("```", "").strip()

                telemetry = _telemetry(candidate_model, started=started, usage=usage)
                if candidate_model != model:
                    telemetry["fallback_model"] = candidate_model
                    telemetry["primary_model"] = model
                return {
                    "sql": text,
                    "text": text,
                    "telemetry": telemetry,
                }
            except (APIConnectionError, APITimeoutError, APIStatusError, APIError, httpx.HTTPError, RuntimeError) as exc:
                last_error = _log_openai_exception(
                    exc,
                    attempt=attempt,
                    attempts=DEFAULT_OPENAI_MAX_ATTEMPTS,
                    operation="chat.completions.create.stream",
                )
                if attempt < DEFAULT_OPENAI_MAX_ATTEMPTS:
                    time.sleep(0.4 * attempt)
                    continue
                break

        if candidate_model != _model_candidates(model)[-1]:
            logger.warning(
                "openai_stream_primary_model_failed attempting_fallback primary_model=%s fallback_model=%s error_type=%s",
                model,
                _model_candidates(model)[-1],
                (last_error or {}).get("error_type"),
            )

    if last_error is not None:
        if len(_model_candidates(model)) > 1:
            last_error["fallback_model"] = _model_candidates(model)[-1]
            last_error["primary_model"] = model
        error_text = _request_error_text(last_error)
        return {
            "sql": error_text,
            "text": error_text,
            "telemetry": _telemetry(model, started=started, error=last_error),
        }

    return {
        "sql": "",
        "text": "",
        "telemetry": _telemetry(model, started=started),
    }
