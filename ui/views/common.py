from __future__ import annotations

from dataclasses import dataclass
import json
import time
from typing import Any, Callable

import pandas as pd
import streamlit as st


@dataclass(frozen=True)
class ViewServices:
    ensure_schema_semantics: Callable[[], Any]
    persist_workspace_memory: Callable[[], Any]
    persist_workspace_preferences: Callable[..., Any]
    build_workspace_report_payload: Callable[..., dict[str, Any]]
    persist_report_view: Callable[..., Any]
    run_monitoring_workflow: Callable[..., Any]
    run_query: Callable[..., Any]
    is_scalar_result: Callable[[Any], bool]
    can_render_chart: Callable[[Any], bool]
    build_column_options: Callable[[Any], list[dict[str, Any]]]
    get_numeric_column_options: Callable[[Any], list[dict[str, Any]]]
    current_chart_state: Callable[[], dict[str, Any]]
    build_ai_recommendations: Callable[..., list[str]]
    persist_query_bookmark: Callable[..., Any]
    persist_investigation_pin: Callable[..., Any]
    persist_investigation_bookmark: Callable[..., Any]
    persist_shared_query_bookmark: Callable[..., Any]
    persist_shared_report_view: Callable[..., Any]
    persist_shared_investigation: Callable[..., Any]
    current_timestamp: Callable[[], str]


def payload_fingerprint(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))


def latest_items(items: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None, limit: int) -> list[dict[str, Any]]:
    return list(reversed(list(items or [])[-limit:]))


def cached_json_bytes(namespace: str, payload: Any, *, indent: int = 2) -> bytes:
    cache = st.session_state.setdefault("_render_export_cache", {})
    key = f"{namespace}:json:{payload_fingerprint(payload)}"
    if key not in cache:
        cache[key] = json.dumps(payload, indent=indent, default=str).encode("utf-8")
    return cache[key]


def dataframe_fingerprint(df: pd.DataFrame) -> str:
    columns = tuple(str(column) for column in df.columns)
    dtypes = tuple(str(dtype) for dtype in df.dtypes)
    row_hash = int(pd.util.hash_pandas_object(df, index=True).sum()) if not df.empty else 0
    return payload_fingerprint({"shape": df.shape, "columns": columns, "dtypes": dtypes, "hash": row_hash})


def cached_dataframe_csv_bytes(namespace: str, df: pd.DataFrame) -> bytes:
    cache = st.session_state.setdefault("_render_export_cache", {})
    key = f"{namespace}:csv:{dataframe_fingerprint(df)}"
    if key not in cache:
        cache[key] = df.to_csv(index=False).encode("utf-8")
    return cache[key]


def record_render_timing(section: str, started_at: float) -> None:
    elapsed_ms = round((time.perf_counter() - started_at) * 1000, 2)
    timings = st.session_state.setdefault("_render_timings", [])
    timings.append({"section": section, "elapsed_ms": elapsed_ms, "timestamp": time.time()})
    st.session_state["_render_timings"] = timings[-30:]
