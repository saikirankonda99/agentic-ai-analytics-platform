from __future__ import annotations

import time

import streamlit as st

from ui.dashboard import render_empty_state_card
from ui.views.common import ViewServices, cached_dataframe_csv_bytes, cached_json_bytes, record_render_timing
from workspace import onboarding_progress, update_onboarding_step


def _filtered_and_sorted_result(df, search: str, sort_column: str, ascending: bool):
    filtered_df = df
    if search.strip():
        needle = search.strip().lower()
        row_mask = df.astype(str).apply(lambda row: row.str.lower().str.contains(needle, regex=False).any(), axis=1)
        filtered_df = df[row_mask]
    if sort_column:
        filtered_df = filtered_df.sort_values(by=sort_column, ascending=ascending, kind="mergesort")
    return filtered_df


def render_result_explorer(df, services: ViewServices, base_filename: str = "result") -> None:
    started_at = time.perf_counter()
    if df is None or df.empty:
        st.markdown(
            render_empty_state_card(
                "Result Explorer",
                "No rows are available for the current workflow.",
                [
                    "Try a broader question such as Revenue by country.",
                    "Inspect SQL validation guidance before retrying.",
                    "Upload a CSV if you want to analyze an external dataset.",
                ],
            ),
            unsafe_allow_html=True,
        )
        record_render_timing("result_explorer_empty", started_at)
        return

    st.markdown(
        """
        <div class="workspace-shell compact-shell">
            <div class="section-title">Result Explorer</div>
            <div class="section-subtitle">Filter, sort, inspect, and export the active result set.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    controls = st.columns([1.4, 1, 0.72], gap="small")
    with controls[0]:
        search = st.text_input(
            "Filter results",
            value=st.session_state.get("result_filter", ""),
            placeholder="Search visible values...",
            help="Filters rows by matching any displayed cell value.",
        )
        if st.session_state.get("result_filter") != search:
            st.session_state.result_filter = search
    with controls[1]:
        sort_options = ["None"] + list(df.columns)
        current_sort = st.session_state.get("result_sort_column") or "None"
        sort_column = st.selectbox(
            "Sort by",
            sort_options,
            index=sort_options.index(current_sort) if current_sort in sort_options else 0,
        )
        next_sort_column = "" if sort_column == "None" else sort_column
        if st.session_state.get("result_sort_column") != next_sort_column:
            st.session_state.result_sort_column = next_sort_column
    with controls[2]:
        ascending = st.toggle("Ascending", value=st.session_state.get("result_sort_ascending", True))
        if st.session_state.get("result_sort_ascending") != ascending:
            st.session_state.result_sort_ascending = ascending

    filtered_df = _filtered_and_sorted_result(
        df,
        st.session_state.get("result_filter", ""),
        st.session_state.get("result_sort_column", ""),
        st.session_state.get("result_sort_ascending", True),
    )
    st.dataframe(filtered_df, width="stretch", height=320)
    st.caption(f"Showing {len(filtered_df):,} of {len(df):,} rows.")
    left, right = st.columns(2, gap="small")
    with left:
        st.download_button(
            "Download Filtered CSV",
            cached_dataframe_csv_bytes(f"{base_filename}-filtered", filtered_df),
            f"{base_filename}-filtered.csv",
            "text/csv",
            width="stretch",
        )
    with right:
        st.download_button(
            "Download Full CSV",
            cached_dataframe_csv_bytes(base_filename, df),
            f"{base_filename}.csv",
            "text/csv",
            width="stretch",
        )
    progress = onboarding_progress(st.session_state.get("workspace_memory", {}))
    if not progress["steps"].get("results_reviewed"):
        memory = update_onboarding_step(st.session_state.get("workspace_memory", {}), "results_reviewed")
        st.session_state.workspace_memory = memory
        services.persist_workspace_memory()
    record_render_timing("result_explorer", started_at)


def render_report_exports(services: ViewServices, scope: str = "analytics") -> None:
    started_at = time.perf_counter()
    payload = services.build_workspace_report_payload(scope=scope)
    summary_text = "\n\n".join(
        part
        for part in [
            f"# {scope.title()} Summary",
            f"Question: {payload.get('question') or 'No active question'}",
            f"Rows: {payload.get('rows', 0)}",
            f"Insight: {payload.get('insight') or 'No insight generated yet.'}",
            f"SQL:\n{payload.get('sql') or 'No SQL generated.'}",
        ]
        if part
    )
    left, middle, right, share = st.columns(4, gap="small")
    with left:
        st.download_button(
            "Executive Summary",
            summary_text.encode("utf-8"),
            f"{scope}-executive-summary.md",
            "text/markdown",
            width="stretch",
        )
    with middle:
        st.download_button(
            "Workflow Trace",
            cached_json_bytes(f"{scope}-workflow-trace", payload.get("trace", [])),
            f"{scope}-workflow-trace.json",
            "application/json",
            width="stretch",
        )
    with right:
        if st.button("Save Report View", width="stretch"):
            services.persist_report_view(scope=scope)
            st.success("Report view saved to this workspace.")
    with share:
        if st.button("Share Report", width="stretch"):
            if services.persist_shared_report_view(scope=scope):
                st.success("Report shared with this workspace.")
    record_render_timing(f"{scope}_report_exports", started_at)
