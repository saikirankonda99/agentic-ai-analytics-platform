from __future__ import annotations

import re
from typing import Any

import pandas as pd


CHART_TYPES = {
    "bar": "Bar",
    "bar chart": "Bar",
    "line": "Line",
    "line chart": "Line",
    "area": "Area",
    "area chart": "Area",
}


def empty_analytics_memory() -> dict[str, Any]:
    return {
        "turns": [],
        "previous_sql": "",
        "previous_question": "",
        "previous_intent": "",
        "previous_dimensions": [],
        "previous_metrics": [],
        "previous_filters": [],
        "previous_chart": {},
        "semantic_summaries": [],
    }


def normalize_memory(memory: dict[str, Any] | None) -> dict[str, Any]:
    normalized = empty_analytics_memory()
    if memory:
        normalized.update(memory)
    return normalized


def _field_names(items: list[dict[str, Any]] | None, limit: int = 8) -> list[str]:
    return [str(item.get("name")) for item in (items or [])[:limit] if item.get("name")]


def semantic_memory_summary(context: dict[str, Any] | None) -> dict[str, Any]:
    if not context:
        return {}
    return {
        "name": context.get("name", "Dataset"),
        "summary": context.get("summary", ""),
        "dimensions": _field_names(context.get("dimensions", []) + context.get("categorical_fields", [])),
        "metrics": _field_names(context.get("metrics", [])),
        "time_columns": _field_names(context.get("time_columns", [])),
        "identifiers": _field_names(context.get("identifiers", [])),
    }


def extract_followup_context(prompt: str) -> dict[str, Any]:
    lowered = prompt.lower().strip()
    filters: list[str] = []
    time_window = ""
    comparison = ""
    chart_type = ""

    for pattern in (
        r"\bonly\s+(?:in|for|from)\s+([a-z0-9 ._-]+)",
        r"\b(?:in|for|from)\s+([a-z][a-z0-9 ._-]+)$",
        r"\bwhere\s+([a-z0-9 ._=-]+)",
    ):
        match = re.search(pattern, lowered)
        if match:
            filters.append(match.group(1).strip(" ."))
            break

    time_match = re.search(r"\blast\s+(\d+)\s+(day|days|week|weeks|month|months|quarter|quarters|year|years)\b", lowered)
    if time_match:
        time_window = f"last {time_match.group(1)} {time_match.group(2)}"
    elif "previous year" in lowered or "last year" in lowered:
        time_window = "previous year"

    if "compare to previous year" in lowered or "year over year" in lowered or "yoy" in lowered:
        comparison = "compare to previous year"

    for key, value in CHART_TYPES.items():
        if re.search(rf"\b{re.escape(key)}\b", lowered):
            chart_type = value
            break

    return {
        "filters": filters,
        "time_window": time_window,
        "comparison": comparison,
        "chart_type": chart_type,
    }


def is_chart_only_followup(prompt: str, memory: dict[str, Any] | None) -> bool:
    context = extract_followup_context(prompt)
    if not context.get("chart_type"):
        return False
    if context.get("filters") or context.get("time_window") or context.get("comparison"):
        return False
    normalized = normalize_memory(memory)
    return bool(normalized.get("previous_question") or normalized.get("previous_sql"))


def contextualize_followup(prompt: str, memory: dict[str, Any] | None) -> dict[str, Any]:
    normalized = normalize_memory(memory)
    extracted = extract_followup_context(prompt)
    previous_intent = normalized.get("previous_intent") or normalized.get("previous_question")
    has_previous_context = bool(previous_intent or normalized.get("previous_sql"))
    has_followup_marker = any(
        [
            extracted.get("filters"),
            extracted.get("time_window"),
            extracted.get("comparison"),
            extracted.get("chart_type"),
            re.match(r"^(only|just|same|also|now|then|show as|make it|compare)\b", prompt.lower().strip()),
        ]
    )

    if has_previous_context and has_followup_marker:
        additions = []
        if extracted["filters"]:
            additions.append(f"filtered to {', '.join(extracted['filters'])}")
        if extracted["time_window"]:
            additions.append(f"for the {extracted['time_window']}")
        if extracted["comparison"]:
            additions.append(extracted["comparison"])
        if extracted["chart_type"]:
            additions.append(f"visualized as a {extracted['chart_type'].lower()} chart")
        suffix = "; ".join(additions) if additions else prompt
        effective_question = f"{previous_intent}. Refine this analysis: {suffix}."
        is_followup = True
    else:
        effective_question = prompt
        is_followup = False

    return {
        "original_question": prompt,
        "effective_question": effective_question,
        "is_followup": is_followup,
        **extracted,
    }


def memory_prompt_block(memory: dict[str, Any] | None) -> str:
    normalized = normalize_memory(memory)
    if not normalized.get("previous_question") and not normalized.get("semantic_summaries"):
        return ""

    semantic_summaries = normalized.get("semantic_summaries", [])[-3:]
    semantic_text = "\n".join(
        f"- {item.get('name', 'Dataset')}: {item.get('summary', '')}" for item in semantic_summaries if item
    )
    return (
        "\n\nConversational analytics memory:\n"
        f"Previous question: {normalized.get('previous_question') or 'None'}\n"
        f"Previous contextual intent: {normalized.get('previous_intent') or 'None'}\n"
        f"Previous SQL: {normalized.get('previous_sql') or 'None'}\n"
        f"Previous dimensions: {', '.join(normalized.get('previous_dimensions', [])) or 'None'}\n"
        f"Previous metrics: {', '.join(normalized.get('previous_metrics', [])) or 'None'}\n"
        f"Previous filters: {', '.join(normalized.get('previous_filters', [])) or 'None'}\n"
        f"Previous chart: {normalized.get('previous_chart') or 'None'}\n"
        f"Semantic summaries:\n{semantic_text or '- None'}"
    )


def infer_result_fields(df: pd.DataFrame | None, semantic_context: dict[str, Any] | None) -> tuple[list[str], list[str]]:
    if df is None or df.empty:
        return [], []
    columns = set(str(column) for column in df.columns)
    semantic_context = semantic_context or {}
    dimensions = [
        item.get("name")
        for item in semantic_context.get("time_columns", [])
        + semantic_context.get("categorical_fields", [])
        + semantic_context.get("dimensions", [])
        if item.get("name") in columns
    ]
    metrics = [item.get("name") for item in semantic_context.get("metrics", []) if item.get("name") in columns]
    if not dimensions:
        dimensions = [str(column) for column in df.columns if not pd.api.types.is_numeric_dtype(df[column])][:4]
    if not metrics:
        metrics = [str(column) for column in df.columns if pd.api.types.is_numeric_dtype(df[column])][:4]
    return dimensions[:6], metrics[:6]


def update_analytics_memory(
    memory: dict[str, Any] | None,
    *,
    question: str,
    effective_question: str,
    sql: str,
    df: pd.DataFrame | None,
    semantic_context: dict[str, Any] | None,
    chart_state: dict[str, Any] | None,
) -> dict[str, Any]:
    normalized = normalize_memory(memory)
    dimensions, metrics = infer_result_fields(df, semantic_context)
    extracted = extract_followup_context(question)
    semantic_summary = semantic_memory_summary(semantic_context)
    semantic_summaries = list(normalized.get("semantic_summaries", []))
    if semantic_summary and semantic_summary not in semantic_summaries:
        semantic_summaries.append(semantic_summary)

    turn = {
        "question": question,
        "effective_question": effective_question,
        "sql": sql,
        "dimensions": dimensions,
        "metrics": metrics,
        "filters": extracted.get("filters", []),
        "chart": chart_state or {},
    }
    turns = (list(normalized.get("turns", [])) + [turn])[-8:]

    normalized.update(
        {
            "turns": turns,
            "previous_sql": sql or normalized.get("previous_sql", ""),
            "previous_question": question,
            "previous_intent": effective_question,
            "previous_dimensions": dimensions,
            "previous_metrics": metrics,
            "previous_filters": extracted.get("filters", []),
            "previous_chart": chart_state or normalized.get("previous_chart", {}),
            "semantic_summaries": semantic_summaries[-5:],
        }
    )
    return normalized
