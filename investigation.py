from __future__ import annotations

import time
from typing import Any, Callable

from db import get_schema, run_query as run_sql_query
from guardrails import is_safe_sql
from llm import DEFAULT_SQL_MODEL, generate_sql_with_telemetry
from semantic import semantic_prompt_block


InvestigationCallback = Callable[[str, str, str], None]


def empty_investigation_state() -> dict[str, Any]:
    return {
        "status": "idle",
        "severity": "info",
        "queries": [],
        "summary": "No autonomous investigation has run yet.",
        "lifecycle": [],
        "evidence": [],
        "score": 0.0,
        "reasoning_trace": [],
        "telemetry": {
            "steps": [],
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "cost_usd": 0.0,
            "latency_ms": 0,
            "model": "",
            "usage_available": False,
        },
    }


def investigation_lifecycle_event(stage: str, status: str, detail: str) -> dict[str, Any]:
    return {
        "stage": stage,
        "status": status,
        "detail": detail,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }


def score_investigation(state: dict[str, Any]) -> float:
    queries = state.get("queries", [])
    if not queries:
        return 0.0
    successful = len([item for item in queries if item.get("status") == "success"])
    evidence = len(state.get("evidence", []))
    severity_weight = {"info": 0.1, "warning": 0.2, "critical": 0.3}.get(state.get("severity", "info"), 0.1)
    return round(min(1.0, successful / max(len(queries), 1) * 0.55 + min(evidence, 4) * 0.05 + severity_weight), 2)


def should_investigate(insight_state: dict[str, Any] | None) -> bool:
    if not insight_state:
        return False
    return insight_state.get("severity") in {"warning", "critical"} and bool(insight_state.get("findings"))


def _record_telemetry(current: dict[str, Any], step: dict[str, Any]) -> dict[str, Any]:
    telemetry = dict(current or empty_investigation_state()["telemetry"])
    steps = list(telemetry.get("steps", [])) + [step]
    latest_error = next((item for item in reversed(steps) if item.get("error_type") or item.get("error_message")), {})
    telemetry.update(
        {
            "steps": steps,
            "prompt_tokens": sum(item.get("prompt_tokens", 0) for item in steps),
            "completion_tokens": sum(item.get("completion_tokens", 0) for item in steps),
            "total_tokens": sum(item.get("total_tokens", 0) for item in steps),
            "cost_usd": sum(item.get("cost_usd", 0.0) for item in steps),
            "latency_ms": sum(item.get("latency_ms", 0) for item in steps),
            "model": step.get("model") or telemetry.get("model") or DEFAULT_SQL_MODEL,
            "usage_available": any(item.get("usage_available", False) for item in steps),
            "error_type": latest_error.get("error_type"),
            "error_message": latest_error.get("error_message"),
            "error_details": latest_error.get("error_details"),
        }
    )
    return telemetry


def _finding_priority(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    severity_rank = {"critical": 0, "warning": 1, "info": 2}
    return sorted(findings, key=lambda item: severity_rank.get(item.get("severity", "info"), 3))


def _investigation_prompt(
    question: str,
    base_sql: str,
    finding: dict[str, Any],
    semantic_context: dict[str, Any] | None,
) -> str:
    return f"""
Create one targeted SQLite read-only investigation query for the detected analytics signal.

Original analytical question:
{question}

Previous SQL:
{base_sql}

Detected finding:
Type: {finding.get("type", "signal")}
Severity: {finding.get("severity", "info")}
Title: {finding.get("title", "")}
Detail: {finding.get("detail", "")}
Metric: {finding.get("metric", "")}
Dimension: {finding.get("dimension", "")}

Investigation goal:
- Compare likely contributing dimensions or time periods.
- Surface likely root-cause segments.
- Keep the query narrow and return no more than 25 rows.
- Return ONLY raw SQL.
{semantic_prompt_block(semantic_context)}
"""


def _result_summary(columns: list[str], rows: list[Any]) -> str:
    if not columns:
        return "No columns returned."
    if not rows:
        return "Investigation query returned no rows."
    first_row = rows[0]
    preview = ", ".join(f"{column}={value}" for column, value in zip(columns, first_row))
    return f"Returned {len(rows)} row(s). Leading result: {preview}."


def investigation_prompt_block(investigation_state: dict[str, Any] | None) -> str:
    if not investigation_state or investigation_state.get("status") in {"idle", "skipped"}:
        return ""
    queries = investigation_state.get("queries", [])
    query_text = "\n".join(
        (
            f"- [{item.get('status', 'unknown')}] {item.get('finding_title', 'Investigation')}: "
            f"{item.get('summary', '')}"
        )
        for item in queries
    )
    return (
        "\n\nAutonomous drill-down investigation:\n"
        f"Status: {investigation_state.get('status', 'idle')}\n"
        f"Summary: {investigation_state.get('summary', '')}\n"
        f"{query_text or '- No investigation queries executed.'}"
    )


def run_investigation(
    question: str,
    base_sql: str,
    insight_state: dict[str, Any],
    semantic_context: dict[str, Any] | None,
    *,
    max_queries: int = 3,
    callback: InvestigationCallback | None = None,
) -> dict[str, Any]:
    if not should_investigate(insight_state):
        return {
            **empty_investigation_state(),
            "status": "skipped",
            "summary": "Investigation skipped because no warning or critical insight was detected.",
        }

    started = time.perf_counter()
    state = {
        **empty_investigation_state(),
        "status": "running",
        "severity": insight_state.get("severity", "warning"),
        "summary": "Autonomous investigation is running.",
    }
    state["lifecycle"].append(investigation_lifecycle_event("planning", "completed", "Investigation plan created from insight findings."))
    state["reasoning_trace"].append(
        {
            "stage": "planning",
            "summary": "Prioritized warning and critical findings, then generated narrow SQL probes.",
            "findings_considered": len(insight_state.get("findings", [])),
        }
    )
    findings = _finding_priority(insight_state.get("findings", []))[:max_queries]
    schema = get_schema()

    for index, finding in enumerate(findings, start=1):
        if callback:
            callback("active", "investigation", f"Generating drill-down query {index} of {len(findings)}.")

        generation = generate_sql_with_telemetry(
            _investigation_prompt(question, base_sql, finding, semantic_context),
            schema,
        )
        telemetry_step = {"step": "investigation", **generation.get("telemetry", {})}
        state["telemetry"] = _record_telemetry(state["telemetry"], telemetry_step)
        sql = (generation.get("sql") or "").strip()
        query_record = {
            "finding_title": finding.get("title", "Investigation"),
            "finding_type": finding.get("type", "signal"),
            "severity": finding.get("severity", "info"),
            "sql": sql,
            "status": "pending",
            "summary": "",
        }

        if not sql or sql.startswith("ERROR:"):
            query_record.update({"status": "error", "summary": sql or "SQL generation failed."})
            state["queries"].append(query_record)
            state["lifecycle"].append(investigation_lifecycle_event("query_generation", "failed", query_record["summary"]))
            if callback:
                callback("warning", "investigation", query_record["summary"])
            continue

        if not is_safe_sql(sql):
            query_record.update({"status": "blocked", "summary": "Investigation query blocked by SQL guardrails."})
            state["queries"].append(query_record)
            state["lifecycle"].append(investigation_lifecycle_event("guardrails", "blocked", query_record["summary"]))
            if callback:
                callback("warning", "investigation", query_record["summary"])
            continue

        if callback:
            callback("active", "investigation", f"Executing drill-down query {index}.")
        try:
            columns, rows = run_sql_query(sql)
            query_record.update(
                {
                    "status": "success",
                    "columns": columns,
                    "row_count": len(rows),
                    "summary": _result_summary(columns, rows),
                }
            )
            state["evidence"].append(
                {
                    "finding_title": query_record["finding_title"],
                    "row_count": len(rows),
                    "columns": columns,
                    "summary": query_record["summary"],
                }
            )
            state["lifecycle"].append(investigation_lifecycle_event("evidence_collection", "completed", query_record["summary"]))
            if callback:
                callback("completed", "investigation", query_record["summary"])
        except Exception as exc:
            query_record.update({"status": "error", "summary": str(exc)})
            state["lifecycle"].append(investigation_lifecycle_event("evidence_collection", "failed", str(exc)))
            if callback:
                callback("warning", "investigation", str(exc))
        state["queries"].append(query_record)

    successful = [item for item in state["queries"] if item.get("status") == "success"]
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    state["telemetry"]["latency_ms"] += elapsed_ms
    state["status"] = "completed" if successful else "failed"
    if successful:
        state["summary"] = f"Investigation completed with {len(successful)} successful drill-down query(s)."
    else:
        state["summary"] = "Investigation ran but did not produce a successful drill-down query."
    state["score"] = score_investigation(state)
    state["lifecycle"].append(investigation_lifecycle_event("summary", state["status"], state["summary"]))
    return state
