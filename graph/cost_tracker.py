"""
Cost and usage tracker.

Logs every query's model, token counts, and estimated cost to a local SQLite
database (data/cost_log.db). The Streamlit admin tab reads this to render
the cost dashboard.
"""

from __future__ import annotations

import os
import sqlite3
from datetime import UTC, datetime

_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "cost_log.db")

# approximate cost per 1M tokens (update when OpenAI changes pricing)
_COST_PER_1M = {
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
    "claude-sonnet-4-20250514": {"input": 3.00, "output": 15.00},
}


def _get_conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(_DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS query_log (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            ts         TEXT    NOT NULL,
            question   TEXT,
            model      TEXT,
            input_tok  INTEGER,
            output_tok INTEGER,
            cost_usd   REAL,
            latency_ms INTEGER
        )
    """)
    conn.commit()
    return conn


def log_query_cost(
    question: str,
    model: str,
    cost_usd: float,
    tokens: int,
    latency_ms: int = 0,
) -> None:
    conn = _get_conn()
    conn.execute(
        "INSERT INTO query_log (ts, question, model, input_tok, output_tok, cost_usd, latency_ms) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (datetime.now(UTC).isoformat(), question, model, tokens, 0, cost_usd, latency_ms),
    )
    conn.commit()
    conn.close()


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate cost in USD from token counts."""
    rates = _COST_PER_1M.get(model, {"input": 2.50, "output": 10.00})
    return (input_tokens * rates["input"] + output_tokens * rates["output"]) / 1_000_000


def get_total_cost() -> float:
    conn = _get_conn()
    row = conn.execute("SELECT COALESCE(SUM(cost_usd), 0) FROM query_log").fetchone()
    conn.close()
    return row[0]


def get_recent_queries(limit: int = 20) -> list[dict]:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT ts, question, model, input_tok, cost_usd, latency_ms "
        "FROM query_log ORDER BY id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return [
        {
            "ts": r[0], "question": r[1], "model": r[2],
            "tokens": r[3], "cost_usd": r[4], "latency_ms": r[5],
        }
        for r in rows
    ]
