from __future__ import annotations

import re
from typing import Any

import pandas as pd


IDENTIFIER_HINTS = ("id", "key", "code", "number", "no", "uuid")
TIME_HINTS = ("date", "time", "year", "month", "day", "created", "updated", "timestamp")
METRIC_HINTS = ("amount", "total", "sum", "count", "qty", "quantity", "price", "cost", "revenue", "sales", "rate", "duration")


def _clean_name(value: object) -> str:
    return str(value or "").strip()


def _matches_hint(name: str, hints: tuple[str, ...]) -> bool:
    normalized = re.sub(r"[^a-z0-9]+", "_", name.lower())
    return any(hint in normalized.split("_") or normalized.endswith(f"_{hint}") for hint in hints)


def infer_column_role(name: str, series: pd.Series | None = None, dtype: str | None = None) -> str:
    lowered = name.lower()
    dtype_text = (dtype or str(series.dtype if series is not None else "")).lower()

    if _matches_hint(lowered, TIME_HINTS) or "date" in dtype_text or "time" in dtype_text:
        return "time"
    if lowered == "id" or lowered.endswith("id") or _matches_hint(lowered, IDENTIFIER_HINTS):
        return "identifier"
    if series is not None:
        if pd.api.types.is_numeric_dtype(series):
            unique_ratio = series.nunique(dropna=True) / max(len(series), 1)
            if unique_ratio > 0.92 and ("int" in dtype_text or lowered.endswith("id")):
                return "identifier"
            return "metric"
        if pd.api.types.is_datetime64_any_dtype(series):
            return "time"
        if series.nunique(dropna=True) <= min(30, max(3, int(len(series) * 0.35))):
            return "categorical"
        return "dimension"
    if any(token in dtype_text for token in ("int", "real", "numeric", "float", "double", "decimal")):
        return "metric" if _matches_hint(lowered, METRIC_HINTS) else "identifier" if _matches_hint(lowered, IDENTIFIER_HINTS) else "metric"
    if any(token in dtype_text for token in ("date", "time")):
        return "time"
    return "dimension"


def profile_dataframe(df: pd.DataFrame, name: str = "Active dataset") -> dict[str, Any]:
    columns: list[dict[str, Any]] = []
    for column in df.columns:
        series = df[column]
        role = infer_column_role(str(column), series=series)
        columns.append(
            {
                "name": str(column),
                "dtype": str(series.dtype),
                "role": role,
                "unique": int(series.nunique(dropna=True)),
                "missing": int(series.isna().sum()),
            }
        )
    return build_semantic_context(name=name, row_count=len(df), columns=columns, source="dataframe")


def parse_schema_tables(schema: str) -> list[dict[str, Any]]:
    tables = []
    for block in re.split(r"\n\s*\n", schema or ""):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines or not lines[0].lower().startswith("table:"):
            continue
        table_name = lines[0].split(":", 1)[1].strip()
        column_text = " ".join(lines[1:])
        columns = []
        for raw_name, raw_type in re.findall(r"([^,()]+)\s*\(([^)]+)\)", column_text):
            name = _clean_name(raw_name)
            dtype = _clean_name(raw_type)
            columns.append({"name": name, "dtype": dtype, "role": infer_column_role(name, dtype=dtype)})
        tables.append({"name": table_name, "columns": columns})
    return tables


def profile_schema(schema: str, name: str = "SQL schema") -> dict[str, Any]:
    tables = parse_schema_tables(schema)
    columns = []
    for table in tables:
        for column in table["columns"]:
            columns.append({**column, "table": table["name"]})
    return build_semantic_context(name=name, row_count=None, columns=columns, source="schema", tables=tables)


def build_semantic_context(
    name: str,
    row_count: int | None,
    columns: list[dict[str, Any]],
    source: str,
    tables: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    roles = {
        "dimensions": [col for col in columns if col["role"] == "dimension"],
        "metrics": [col for col in columns if col["role"] == "metric"],
        "time_columns": [col for col in columns if col["role"] == "time"],
        "identifiers": [col for col in columns if col["role"] == "identifier"],
        "categorical_fields": [col for col in columns if col["role"] == "categorical"],
    }
    context = {
        "name": name,
        "source": source,
        "row_count": row_count,
        "column_count": len(columns),
        "columns": columns,
        "tables": tables or [],
        **roles,
    }
    context["summary"] = semantic_summary(context)
    return context


def _names(items: list[dict[str, Any]], limit: int = 8) -> str:
    names = [item.get("name", "") for item in items[:limit]]
    return ", ".join(name for name in names if name) or "None detected"


def semantic_summary(context: dict[str, Any]) -> str:
    row_text = f"{context['row_count']:,} rows" if context.get("row_count") is not None else f"{len(context.get('tables', []))} tables"
    return (
        f"{context.get('name', 'Dataset')} semantic profile: {row_text}, {context.get('column_count', 0)} columns. "
        f"Metrics: {_names(context.get('metrics', []))}. "
        f"Dimensions: {_names(context.get('dimensions', []) + context.get('categorical_fields', []))}. "
        f"Time columns: {_names(context.get('time_columns', []))}. "
        f"Identifiers: {_names(context.get('identifiers', []))}."
    )


def semantic_prompt_block(context: dict[str, Any] | None) -> str:
    if not context:
        return ""
    return (
        "\n\nSemantic dataset context:\n"
        f"{context.get('summary', '')}\n"
        f"Metric fields: {_names(context.get('metrics', []), 12)}\n"
        f"Dimension fields: {_names(context.get('dimensions', []) + context.get('categorical_fields', []), 12)}\n"
        f"Time fields: {_names(context.get('time_columns', []), 12)}\n"
        f"Identifier fields: {_names(context.get('identifiers', []), 12)}"
    )


def recommend_chart_fields(df: pd.DataFrame, context: dict[str, Any] | None) -> tuple[str | None, str | None]:
    if df.empty or not context:
        return None, None
    columns = set(df.columns)
    dimension_candidates = [
        item["name"]
        for item in context.get("time_columns", []) + context.get("categorical_fields", []) + context.get("dimensions", [])
        if item.get("name") in columns
    ]
    metric_candidates = [item["name"] for item in context.get("metrics", []) if item.get("name") in columns]
    return (dimension_candidates[0] if dimension_candidates else None, metric_candidates[0] if metric_candidates else None)
