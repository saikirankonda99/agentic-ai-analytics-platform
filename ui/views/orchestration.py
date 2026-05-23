from __future__ import annotations

import time

import pandas as pd
import streamlit as st

from backend.operations import operations_summary
from backend.recommendations import autonomous_recommendations, recommendation_messages
from backend.telemetry import validate_telemetry_payload
from ui.dashboard import (
    escape_html,
    next_plotly_key,
    render_active_agent_monitoring,
    render_chat_history,
    render_kpi_cards,
    render_orchestration_status_badges,
    render_recommendation_card,
    render_response_card,
    render_telemetry_panel,
    render_workflow_timeline,
    render_workflow_timeline_cards,
)
from ui.views.common import ViewServices, record_render_timing
from ui.views.reports import render_report_exports
from workspace import retrieve_workspace_context


def render_copilot_workspace() -> None:
    started_at = time.perf_counter()
    active_trace = st.session_state.live_trace or st.session_state.workflow_trace
    active_telemetry = st.session_state.live_telemetry or st.session_state.workflow_telemetry
    st.markdown(
        render_orchestration_status_badges(
            active_trace,
            active_telemetry,
            is_executing=st.session_state.get("is_executing", False),
        ),
        unsafe_allow_html=True,
    )
    left, right = st.columns([0.92, 1.08])
    with left:
        render_chat_history(st.session_state.messages)
        st.markdown(
            render_active_agent_monitoring(
                active_trace,
                active_telemetry,
                is_executing=st.session_state.get("is_executing", False),
            ),
            unsafe_allow_html=True,
        )
    with right:
        render_workflow_timeline(st.session_state.workflow_trace, chart_key=next_plotly_key("workflow_chart_copilot"))
        st.markdown(render_workflow_timeline_cards(active_trace), unsafe_allow_html=True)
        render_telemetry_panel(st.session_state.workflow_telemetry)
        if st.session_state.latest_df is not None:
            st.markdown(
                """
                <div class="section-card compact-card">
                    <div class="section-title">Active Dataset Snapshot</div>
                    <div class="section-subtitle">Fast peek at the current result set powering the workspace.</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.dataframe(st.session_state.latest_df.head(20), width="stretch", height=280)
    record_render_timing("copilot_workspace", started_at)


def current_operations_summary() -> dict:
    return operations_summary(
        memory=st.session_state.get("workspace_memory", {}),
        telemetry=st.session_state.live_telemetry or st.session_state.workflow_telemetry,
        trace=st.session_state.live_trace or st.session_state.workflow_trace,
        execution_graph=st.session_state.get("latest_execution_graph", {}),
        is_executing=st.session_state.get("is_executing", False),
    )


def render_health_banner(summary: dict) -> None:
    tone = "observability-module" if summary.get("health") != "degraded" else "insight-module"
    message = (
        "Runtime degraded. Inspect OpenAI request diagnostics, recovery telemetry, and recent failed phases."
        if summary.get("health") == "degraded"
        else "Runtime healthy. Orchestration telemetry, workspace memory, and diagnostics are available."
    )
    st.markdown(
        render_response_card(
            "Runtime Health",
            f'Current posture: {summary.get("health", "unknown").title()}',
            f'<div class="workspace-body-copy">{escape_html(message)}</div>',
            tone=tone,
        ),
        unsafe_allow_html=True,
    )


def render_operations_center(services: ViewServices, render_telemetry_exports) -> None:
    started_at = time.perf_counter()
    telemetry = validate_telemetry_payload(st.session_state.live_telemetry or st.session_state.workflow_telemetry)
    trace = st.session_state.live_trace or st.session_state.workflow_trace
    memory = st.session_state.get("workspace_memory", {})
    graph = st.session_state.get("latest_execution_graph", {})
    summary = current_operations_summary()
    render_health_banner(summary)
    render_kpi_cards(
        [
            {"label": "Active Workflows", "value": summary["active_workflows"], "caption": "Local workspace workflows currently executing."},
            {"label": "Agent Utilization", "value": summary["active_agents"], "caption": "Agents in running or retrying states."},
            {"label": "Token Volume", "value": f'{summary["total_tokens"]:,}', "caption": "Persisted and active workflow token usage."},
            {"label": "Runtime Cost", "value": f'${summary["estimated_cost_usd"]:.4f}', "caption": "Estimated model spend across workspace telemetry."},
        ]
    )
    left, right = st.columns([1.2, 0.8], gap="medium")
    with left:
        st.markdown(render_workflow_timeline_cards(trace), unsafe_allow_html=True)
        st.markdown(
            render_response_card(
                "Workflow Queue",
                "Workspace-local queue and replay posture from persisted sessions.",
                "".join(
                    f'<div class="workspace-list-item"><div class="observability-label">{escape_html(item.get("run_id", "workflow"))} · {escape_html(item.get("status", "unknown")).upper()}</div>'
                    f'<div class="workspace-body-copy">Trace events: {escape_html(len(item.get("trace", [])))}</div></div>'
                    for item in reversed(memory.get("workflow_runs", [])[-8:])
                )
                or '<div class="workspace-body-copy">No persisted workflow queue entries yet.</div>',
                tone="default-module",
            ),
            unsafe_allow_html=True,
        )
        trend_rows = memory.get("telemetry_summaries", [])[-12:]
        if trend_rows:
            trend_df = pd.DataFrame(trend_rows)
            trend_cols = [col for col in ["latency_ms", "total_tokens", "cost_usd"] if col in trend_df.columns]
            if trend_cols:
                st.line_chart(trend_df[trend_cols], height=260)
        else:
            st.markdown(
                render_response_card(
                    "Telemetry Trends",
                    "Rolling latency, token, and cost trends will appear after workflow runs.",
                    '<div class="workspace-body-copy">No telemetry trend history has been captured yet.</div>',
                    tone="observability-module",
                ),
                unsafe_allow_html=True,
            )
    with right:
        st.markdown(render_active_agent_monitoring(trace, telemetry, st.session_state.get("is_executing", False)), unsafe_allow_html=True)
        st.markdown(
            render_execution_graph_card(
                graph,
                st.session_state.get("latest_stage_confidence", {}),
                st.session_state.get("latest_recovery", {}),
                st.session_state.get("latest_policy_decision", {}),
            ),
            unsafe_allow_html=True,
        )
        recommendation_cards = autonomous_recommendations(
            operations=summary,
            memory=memory,
            investigation=st.session_state.get("investigation_state"),
            telemetry=telemetry,
        )
        st.markdown(render_recommendation_card(recommendation_messages(recommendation_cards)), unsafe_allow_html=True)
        render_telemetry_exports(telemetry, trace, services, scope="operations")
        render_report_exports(services, scope="operations")
    record_render_timing("operations_center", started_at)


def render_execution_graph_card(graph, confidence, recovery, policy_decision=None):
    nodes = graph.get("nodes", []) if graph else []
    body = "".join(
        (
            f'<div class="workspace-list-item"><div class="observability-label">{escape_html(node.get("name", ""))} · {escape_html(node.get("status", "queued")).upper()}</div>'
            f'<div class="workspace-body-copy">Phase: {escape_html(node.get("phase", ""))}<br/>'
            f'Dependencies: {escape_html(", ".join(node.get("dependencies", [])) or "none")}<br/>'
            f'Confidence: {escape_html(node.get("confidence", 0.0))}</div></div>'
        )
        for node in nodes
    )
    if recovery:
        body += (
            f'<div class="workspace-list-item"><div class="observability-label">Recovery · {escape_html(recovery.get("strategy", "none"))}</div>'
            f'<div class="workspace-body-copy">{escape_html(recovery.get("message", ""))}</div></div>'
        )
    if confidence:
        body += (
            '<div class="workspace-list-item"><div class="observability-label">Stage Confidence</div><div class="workspace-body-copy">'
            + "<br/>".join(f"{escape_html(k)}: {escape_html(v)}" for k, v in confidence.items())
            + "</div></div>"
        )
    if policy_decision:
        body += (
            '<div class="workspace-list-item">'
            f'<div class="observability-label">Policy Decision · {escape_html(policy_decision.get("action", "continue")).upper()}</div>'
            f'<div class="workspace-body-copy">{escape_html(policy_decision.get("reason", ""))}<br/>'
            f'Stage: {escape_html(policy_decision.get("stage", ""))}<br/>'
            f'Retry Budget: {escape_html(policy_decision.get("retry_count", 0))}/{escape_html(policy_decision.get("max_retries", 0))}</div></div>'
        )
    return render_response_card(
        "Execution Graph",
        "Coordinator view of agent dependencies, stage state, retry posture, and confidence scores.",
        body or '<div class="workspace-body-copy">No execution graph has been created yet.</div>',
        tone="observability-module",
    )


def render_memory_inspection_card(memory):
    categories = {
        "schema_memory": len((memory or {}).get("semantic_dataset_memory", {})),
        "workflow_memory": len((memory or {}).get("workflow_runs", [])),
        "investigation_memory": len((memory or {}).get("investigations", [])),
        "telemetry_memory": len((memory or {}).get("telemetry_summaries", [])),
    }
    recent_queries = retrieve_workspace_context(memory or {}, st.session_state.get("latest_question", ""), limit=5)
    body = '<div class="observability-grid">' + "".join(
        f'<div class="observability-metric"><div class="observability-label">{escape_html(key)}</div>'
        f'<div class="observability-value">{escape_html(value)}</div></div>'
        for key, value in categories.items()
    ) + "</div>"
    body += "".join(
        f'<div class="workspace-list-item"><div class="observability-label">Retrieval candidate · {escape_html(item.get("run_id", ""))}</div>'
        f'<div class="workspace-body-copy">{escape_html(item.get("question", ""))}<br/>Rows: {escape_html(item.get("rows", 0))}<br/>'
        f'Confidence: {escape_html(item.get("retrieval_confidence", 0.0))}</div></div>'
        for item in recent_queries
    )
    return render_response_card("Semantic Memory Inspection", "Categorized workspace memory with deduplicated recent retrieval candidates.", body, tone="default-module")


def render_session_replay_card(memory):
    sessions = list(reversed((memory or {}).get("sessions", [])[-5:]))
    body = "".join(
        f'<div class="workspace-list-item"><div class="observability-label">{escape_html(session.get("session_id", ""))} · {escape_html(session.get("status", ""))}</div>'
        f'<div class="workspace-body-copy">Started: {escape_html(session.get("started_at", ""))}<br/>'
        f'Workflows: {escape_html(len(session.get("workflow_ids", [])))}<br/>'
        f'Transcripts: {escape_html(len(session.get("transcripts", [])))}</div></div>'
        for session in sessions
    )
    return render_response_card("Session Replay", "Persisted workspace sessions and exportable workflow transcript counts.", body or '<div class="workspace-body-copy">No persisted sessions yet.</div>', tone="summary-module")
