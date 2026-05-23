from __future__ import annotations

import time

import pandas as pd
import streamlit as st

from backend.telemetry import phase_latency_breakdown, telemetry_export_rows, validate_telemetry_payload
from ui.dashboard import (
    escape_html,
    render_active_agent_monitoring,
    render_analytics_memory_card,
    render_executive_briefing_card,
    render_kpi_cards,
    render_monitoring_card,
    render_response_card,
    render_workflow_timeline_cards,
)
from ui.views.common import ViewServices, cached_dataframe_csv_bytes, cached_json_bytes, latest_items, record_render_timing
from ui.views.orchestration import render_execution_graph_card, render_memory_inspection_card


def render_telemetry_exports(telemetry, trace, services: ViewServices, scope: str = "workspace") -> None:
    started_at = time.perf_counter()
    telemetry = validate_telemetry_payload(telemetry)
    rows = telemetry_export_rows(telemetry, trace)
    payload = {
        "telemetry": telemetry,
        "trace": trace,
        "events": st.session_state.get("streaming_workflow", {}).get("telemetry_events", []),
        "latency_breakdown": phase_latency_breakdown(telemetry),
        "exported_at": services.current_timestamp(),
    }
    left, right = st.columns(2)
    with left:
        st.download_button(
            "Export Telemetry JSON",
            cached_json_bytes(f"{scope}-telemetry", payload),
            f"{scope}-telemetry.json",
            "application/json",
            width="stretch",
        )
    with right:
        csv_df = pd.DataFrame(rows or [{"correlation_id": telemetry.get("correlation_id"), "step": "none"}])
        st.download_button(
            "Export Telemetry CSV",
            cached_dataframe_csv_bytes(f"{scope}-telemetry", csv_df),
            f"{scope}-telemetry.csv",
            "text/csv",
            width="stretch",
        )
    record_render_timing(f"{scope}_telemetry_exports", started_at)


def render_platform_summary() -> None:
    started_at = time.perf_counter()
    telemetry = validate_telemetry_payload(st.session_state.live_telemetry or st.session_state.workflow_telemetry)
    trace = st.session_state.live_trace or st.session_state.workflow_trace
    latest = trace[-1] if trace else {}
    summary = [
        {
            "label": "Correlation ID",
            "value": telemetry.get("correlation_id", "Pending"),
            "caption": "Stable workflow identifier for support, logs, and telemetry exports.",
        },
        {
            "label": "Workflow State",
            "value": latest.get("status", "standby").title(),
            "caption": latest.get("detail", "No workflow is currently running."),
        },
        {
            "label": "Latency",
            "value": f'{telemetry.get("latency_ms", 0)} ms',
            "caption": "Aggregated across model, memory, execution, and investigation phases.",
        },
        {
            "label": "Cost",
            "value": f'${telemetry.get("cost_usd", 0.0):.4f}',
            "caption": "Estimated model spend for the active workflow.",
        },
    ]
    render_kpi_cards(summary)
    record_render_timing("platform_summary", started_at)


def render_monitoring_workspace(services: ViewServices) -> None:
    started_at = time.perf_counter()
    render_platform_summary()
    memory = st.session_state.get("workspace_memory", {})
    telemetry_runs = memory.get("telemetry_summaries", [])
    failed_count = sum(1 for item in telemetry_runs if item.get("error_type"))
    avg_latency = sum(item.get("latency_ms", 0) for item in telemetry_runs) / len(telemetry_runs) if telemetry_runs else 0
    render_kpi_cards(
        [
            {"label": "Workflow Throughput", "value": len(memory.get("workflow_runs", [])), "caption": "Persisted workflow runs in this workspace."},
            {"label": "Rolling Latency", "value": f"{avg_latency:.0f} ms" if telemetry_runs else "Standby", "caption": "Average latency across persisted telemetry summaries."},
            {"label": "Error Rate", "value": f"{(failed_count / len(telemetry_runs) * 100):.1f}%" if telemetry_runs else "0.0%", "caption": "Share of runs with captured error telemetry."},
            {"label": "Runtime Uptime", "value": "Online", "caption": "Streamlit session and backend diagnostics are responding."},
        ]
    )
    left, right = st.columns([1, 1], gap="medium")
    with left:
        st.markdown(
            render_monitoring_card(st.session_state.get("monitoring_state"), st.session_state.get("monitoring_config")),
            unsafe_allow_html=True,
        )
        st.markdown(render_executive_briefing_card(st.session_state.get("executive_briefing")), unsafe_allow_html=True)
    with right:
        st.markdown(
            render_response_card(
                "Monitoring Run History",
                "Recent scheduled KPI runs with severity and briefing summaries.",
                "".join(
                    f'<div class="workspace-list-item"><div class="observability-label">{escape_html(item.get("time", ""))} · {escape_html(item.get("severity", "info")).upper()}</div>'
                    f'<div class="workspace-body-copy">{escape_html(item.get("summary", ""))}</div></div>'
                    for item in latest_items(st.session_state.get("monitoring_runs", []), 8)
                )
                or '<div class="workspace-body-copy">No monitoring run history yet.</div>',
                tone="observability-module",
            ),
            unsafe_allow_html=True,
        )
        render_telemetry_exports(st.session_state.workflow_telemetry, st.session_state.workflow_trace, services, scope="monitoring")
    record_render_timing("monitoring_workspace", started_at)


def render_agents_workspace(services: ViewServices, agent_utilization) -> None:
    started_at = time.perf_counter()
    telemetry = validate_telemetry_payload(st.session_state.live_telemetry or st.session_state.workflow_telemetry)
    trace = st.session_state.live_trace or st.session_state.workflow_trace
    render_platform_summary()
    left, right = st.columns([0.92, 1.08], gap="medium")
    with left:
        st.markdown(render_active_agent_monitoring(trace, telemetry, st.session_state.get("is_executing", False)), unsafe_allow_html=True)
        st.markdown(render_analytics_memory_card(st.session_state.get("analytics_memory")), unsafe_allow_html=True)
        st.markdown(render_memory_inspection_card(st.session_state.get("workspace_memory", {})), unsafe_allow_html=True)
        streams = st.session_state.get("live_assistant_streams", {})
        st.markdown(
            render_response_card(
                "Agent Reasoning Snapshots",
                "Short-lived streamed artifacts captured during generation, reflection, investigation, and insight phases.",
                "".join(
                    f'<div class="workspace-list-item"><div class="observability-label">{escape_html(phase)}</div>'
                    f'<div class="workspace-body-copy">{escape_html(content).replace(chr(10), "<br/>")}</div></div>'
                    for phase, content in streams.items()
                    if content
                )
                or '<div class="workspace-body-copy">No reasoning snapshots are active for the current workflow.</div>',
                tone="insight-module",
            ),
            unsafe_allow_html=True,
        )
    with right:
        st.markdown(
            render_execution_graph_card(
                st.session_state.get("latest_execution_graph", {}),
                st.session_state.get("latest_stage_confidence", {}),
                st.session_state.get("latest_recovery", {}),
                st.session_state.get("latest_policy_decision", {}),
            ),
            unsafe_allow_html=True,
        )
        validation = st.session_state.get("latest_sql_validation", {})
        explanation = st.session_state.get("latest_sql_explanation", {})
        quality = st.session_state.get("latest_result_quality", {})
        schema_intelligence = st.session_state.get("latest_schema_intelligence", {})
        st.markdown(
            render_response_card(
                "SQL Intelligence",
                "Validation status, schema reasoning, query risk, explanation, and result quality.",
                f'<div class="workspace-body-copy">Validation: {escape_html(validation.get("status", "pending"))}<br/>'
                f'Risk: {escape_html(validation.get("risk_level", "unknown"))} ({escape_html(validation.get("risk_score", 0))})<br/>'
                f'Confidence: {escape_html(validation.get("confidence", 0))}<br/>'
                f'Schema confidence: {escape_html(schema_intelligence.get("confidence", 0))}<br/>'
                f'Intent: {escape_html(explanation.get("intent_summary", ""))}<br/>'
                f'Result quality: {escape_html(quality.get("status", "pending"))} ({escape_html(quality.get("confidence", 0))})</div>'
                + "".join(
                    f'<div class="workspace-list-item"><div class="observability-label">Warning</div><div class="workspace-body-copy">{escape_html(item)}</div></div>'
                    for item in (validation.get("warnings", []) + quality.get("warnings", []))[:5]
                ),
                tone="summary-module",
            ),
            unsafe_allow_html=True,
        )
        st.markdown(render_workflow_timeline_cards(trace), unsafe_allow_html=True)
        breakdown = phase_latency_breakdown(telemetry)
        st.markdown(
            render_response_card(
                "Latency Breakdown",
                "Per-phase runtime profile for model calls, retrieval, execution, and follow-up agents.",
                "".join(
                    f'<div class="workspace-list-item"><div class="observability-label">{escape_html(item["phase"])}</div>'
                    f'<div class="workspace-body-copy">{escape_html(item["latency_ms"])} ms · {escape_html(item["tokens"])} tokens · {escape_html(item["status"])}</div></div>'
                    for item in breakdown
                )
                or '<div class="workspace-body-copy">Run a workflow to populate latency breakdowns.</div>',
                tone="observability-module",
            ),
            unsafe_allow_html=True,
        )
        render_telemetry_exports(telemetry, trace, services, scope="agents")
        utilization = agent_utilization(st.session_state.get("latest_execution_graph", {}))
        if utilization:
            st.dataframe(pd.DataFrame(utilization), width="stretch", height=220)
    record_render_timing("agents_workspace", started_at)
