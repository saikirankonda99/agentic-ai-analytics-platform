import time
import os

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
