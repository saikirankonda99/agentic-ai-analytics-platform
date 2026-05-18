import time
import os
from typing import Callable

from openai import OpenAI
import streamlit as st

from graph.cost_tracker import estimate_cost


def get_openai_api_key():
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        return api_key

    try:
        return st.secrets["OPENAI_API_KEY"]
    except Exception:
        return None


client = OpenAI(api_key=get_openai_api_key())
DEFAULT_SQL_MODEL = "gpt-4.1-mini"


TokenCallback = Callable[[str, str], None]


def generate_sql_with_telemetry(question, schema, model=DEFAULT_SQL_MODEL):
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

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )

        latency_ms = int((time.perf_counter() - started) * 1000)
        usage = getattr(response, "usage", None)
        prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
        completion_tokens = getattr(usage, "completion_tokens", 0) or 0
        total_tokens = getattr(usage, "total_tokens", 0) or (prompt_tokens + completion_tokens)
        usage_available = usage is not None

        return {
            "sql": response.choices[0].message.content.strip().replace("```sql", "").replace("```", ""),
            "telemetry": {
                "model": model,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
                "cost_usd": estimate_cost(model, prompt_tokens, completion_tokens) if usage_available else 0.0,
                "latency_ms": latency_ms,
                "usage_available": usage_available,
            },
        }

    except Exception as e:
        latency_ms = int((time.perf_counter() - started) * 1000)
        return {
            "sql": f"ERROR: {str(e)}",
            "telemetry": {
                "model": model,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "cost_usd": 0.0,
                "latency_ms": latency_ms,
                "usage_available": False,
            },
        }


def generate_sql(question, schema):
    return generate_sql_with_telemetry(question, schema)["sql"]


def stream_sql_with_telemetry(
    question,
    schema,
    model=DEFAULT_SQL_MODEL,
    token_callback: TokenCallback | None = None,
):
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
    prompt,
    model=DEFAULT_SQL_MODEL,
    temperature=0,
    token_callback: TokenCallback | None = None,
    cleanup_sql=False,
):
    started = time.perf_counter()
    last_error = None

    for attempt in range(2):
        content_parts = []
        try:
            try:
                stream = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature,
                    stream=True,
                    stream_options={"include_usage": True},
                )
            except TypeError:
                stream = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature,
                    stream=True,
                )

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

            latency_ms = int((time.perf_counter() - started) * 1000)
            prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
            completion_tokens = getattr(usage, "completion_tokens", 0) or 0
            total_tokens = getattr(usage, "total_tokens", 0) or (prompt_tokens + completion_tokens)
            usage_available = usage is not None

            return {
                "sql": text,
                "text": text,
                "telemetry": {
                    "model": model,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens,
                    "cost_usd": estimate_cost(model, prompt_tokens, completion_tokens) if usage_available else 0.0,
                    "latency_ms": latency_ms,
                    "usage_available": usage_available,
                },
            }

        except Exception as e:
            last_error = e
            if attempt == 0:
                time.sleep(0.4)
                continue

    if last_error is not None:
        latency_ms = int((time.perf_counter() - started) * 1000)
        return {
            "sql": f"ERROR: {str(last_error)}",
            "text": f"ERROR: {str(last_error)}",
            "telemetry": {
                "model": model,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "cost_usd": 0.0,
                "latency_ms": latency_ms,
                "usage_available": False,
            },
        }

    return {
        "sql": "",
        "text": "",
        "telemetry": {
            "model": model,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "cost_usd": 0.0,
            "latency_ms": int((time.perf_counter() - started) * 1000),
            "usage_available": False,
        },
    }
