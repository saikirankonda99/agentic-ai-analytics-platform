from __future__ import annotations

import json

import streamlit as st

from backend.connectors import get_connector_registry
from backend.telemetry import filter_telemetry_events, validate_telemetry_payload
from backend.workspace_inspection import saved_sql_history, workflow_transcripts, workspace_summary
from ui.dashboard import escape_html, render_observability_card, render_response_card
from ui.views.common import ViewServices


def render_api_workspace(services: ViewServices, render_telemetry_exports) -> None:
    telemetry = validate_telemetry_payload(st.session_state.live_telemetry or st.session_state.workflow_telemetry)
    trace = st.session_state.live_trace or st.session_state.workflow_trace
    runtime = st.session_state.get("openai_runtime", {})
    memory = st.session_state.get("workspace_memory", {})
    workspace_report = workspace_summary(memory)
    connector_diagnostics = get_connector_registry().diagnostics(validate=True)
    left, right = st.columns([1, 1], gap="medium")
    with left:
        st.markdown(
            render_response_card(
                "API Runtime Diagnostics",
                "Operational posture for backend, OpenAI runtime, proxy handling, and environment loading.",
                f'<div class="observability-grid">{escape_html("")}</div>'
                f'<div class="workspace-body-copy">Dotenv loaded: {escape_html(runtime.get("dotenv_loaded"))}<br/>'
                f'API key configured: {escape_html(runtime.get("api_key_configured"))}<br/>'
                f'Timeout: {escape_html(runtime.get("timeout_seconds"))}s<br/>'
                f'Proxy trust: {escape_html(runtime.get("trust_env"))}<br/>'
                f'Correlation ID: {escape_html(telemetry.get("correlation_id", "Pending"))}</div>',
                tone="observability-module",
            ),
            unsafe_allow_html=True,
        )
        st.code(
            "GET /health\nGET /ready\nGET /diagnostics\nPOST /execute\nGET /workflow/{workflow_id}\nGET /workflow/{workflow_id}/events\nGET /workflow/{workflow_id}/stream\nGET /connectors\nGET /connectors/{connector_id}/health\nGET /connectors/{connector_id}/schema\nPOST /connectors/validate\nGET /workspace/{workspace_id}/inspection\nGET /workspace/{workspace_id}/transcripts\nGET /workspace/{workspace_id}/sql-history",
            language="http",
        )
        connector_rows = []
        for connector in connector_diagnostics.get("connectors", []):
            health = connector_diagnostics.get("health", {}).get(connector.get("connector_id"), {})
            connector_rows.append(
                f'<div class="workspace-list-item"><div class="observability-label">{escape_html(connector.get("name"))} · {escape_html(connector.get("kind"))}</div>'
                f'<div class="workspace-body-copy">Status: {escape_html(health.get("status", "unknown"))}<br/>'
                f'Latency: {escape_html(health.get("latency_ms", 0))} ms<br/>'
                f'Enabled: {escape_html(connector.get("enabled"))}<br/>'
                f'Message: {escape_html(health.get("message", ""))}</div></div>'
            )
        st.markdown(
            render_response_card(
                "Connector Diagnostics",
                "Startup validation, health, schema readiness, and safe configuration posture.",
                "".join(connector_rows)
                + (
                    '<div class="workspace-body-copy">'
                    f'PostgreSQL configured: {escape_html(connector_diagnostics.get("configuration", {}).get("postgres_configured"))}<br/>'
                    f'PostgreSQL schema: {escape_html(connector_diagnostics.get("configuration", {}).get("postgres_schema"))}<br/>'
                    f'SQLite path: {escape_html(connector_diagnostics.get("configuration", {}).get("sqlite_database_path"))}'
                    "</div>"
                ),
                tone="summary-module",
            ),
            unsafe_allow_html=True,
        )
        st.markdown(
            render_response_card(
                "Workspace Inspection",
                "Session, transcript, saved SQL, memory, and telemetry rollup for the active workspace.",
                f'<div class="workspace-body-copy">Workspace: {escape_html(workspace_report.get("workspace_id"))}<br/>'
                f'Sessions: {escape_html(workspace_report.get("session_count"))}<br/>'
                f'Transcripts: {escape_html(workspace_report.get("transcript_count"))}<br/>'
                f'Saved SQL: {escape_html(len(saved_sql_history(memory)))}<br/>'
                f'Error Rate: {escape_html(workspace_report.get("telemetry", {}).get("error_rate", 0.0))}%</div>',
                tone="summary-module",
            ),
            unsafe_allow_html=True,
        )
        st.download_button(
            "Export Workspace Report",
            data=json.dumps(
                {
                    "summary": workspace_report,
                    "transcripts": workflow_transcripts(memory),
                    "sql_history": saved_sql_history(memory),
                },
                indent=2,
            ),
            file_name="workspace-report.json",
            mime="application/json",
            width="stretch",
        )
    with right:
        st.markdown(render_observability_card(telemetry, trace), unsafe_allow_html=True)
        events = st.session_state.get("streaming_workflow", {}).get("telemetry_events", [])
        search = st.text_input("Telemetry search", placeholder="Filter runtime events by phase, status, or message...")
        filtered_events = filter_telemetry_events(events, query=search)
        st.markdown(
            render_response_card(
                "Telemetry Event Search",
                "Filtered runtime events from the active Streamlit orchestration session.",
                "".join(
                    f'<div class="workspace-list-item"><div class="observability-label">{escape_html(item.get("phase", ""))} · {escape_html(item.get("status", ""))}</div>'
                    f'<div class="workspace-body-copy">{escape_html(item.get("message", ""))}</div></div>'
                    for item in filtered_events[-8:]
                )
                or '<div class="workspace-body-copy">No matching telemetry events for the current workflow.</div>',
                tone="default-module",
            ),
            unsafe_allow_html=True,
        )
        render_telemetry_exports(telemetry, trace, services, scope="api")
