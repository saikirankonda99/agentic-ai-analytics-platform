import os
import time
import json
from datetime import datetime

import pandas as pd
import streamlit as st

from analytics_memory import (
    contextualize_followup,
    empty_analytics_memory,
    is_chart_only_followup,
    memory_prompt_block,
    update_analytics_memory,
)
from autonomous_insights import analyze_result_set, empty_insight_state, insight_prompt_block
from backend.operations import agent_utilization, operations_summary
from backend.recommendations import autonomous_recommendations, recommendation_messages
from backend.services import execute_query_workflow
from backend.telemetry import filter_telemetry_events, phase_latency_breakdown, telemetry_export_rows, validate_telemetry_payload
from backend.workspace_inspection import saved_sql_history, workflow_transcripts, workspace_summary
from db import get_schema
from investigation import (
    empty_investigation_state,
    investigation_prompt_block,
    run_investigation,
    should_investigate,
)
from llm import DEFAULT_SQL_MODEL, stream_text_with_telemetry, validate_openai_runtime
from monitoring import (
    default_monitoring_config,
    empty_briefing_state,
    empty_monitoring_state,
    monitoring_due,
    run_monitoring_checks,
)
from workspace import (
    build_user_session,
    default_user_session,
    default_workspace_memory,
    load_workspace_memory,
    save_workspace_memory,
    snapshot_workspace_run,
    start_workspace_session,
    bookmark_investigation,
    retrieve_workspace_context,
    user_can,
)
from semantic import profile_dataframe, profile_schema, recommend_chart_fields, semantic_prompt_block
from styles.theme import get_theme_css
from ui.dashboard import (
    build_plotly_figure,
    build_default_operations_figure,
    escape_html,
    render_chat_history,
    render_activity_feed,
    render_agent_row,
    render_command_bar,
    render_executive_summary,
    render_footer,
    render_glass_widgets,
    render_hero,
    render_history,
    render_kpi_cards,
    next_plotly_key,
    render_active_agent_monitoring,
    render_analytics_memory_card,
    render_autonomous_insight_card,
    render_investigation_card,
    render_orchestration_status_badges,
    render_executive_briefing_card,
    render_monitoring_card,
    render_workspace_card,
    render_recommendation_card,
    render_result_table_card,
    render_response_card,
    render_semantic_profile_card,
    render_sidebar,
    render_live_execution_panel,
    render_observability_card,
    render_sql_card,
    render_telemetry_panel,
    render_top_navigation,
    render_workflow_timeline,
    render_workflow_timeline_cards,
)

def get_openai_api_key():
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        return api_key

    try:
        return st.secrets["OPENAI_API_KEY"]
    except Exception:
        return None


def is_scalar_result(df):
    return not df.empty and len(df) == 1 and len(df.columns) == 1


def build_column_options(df):
    seen = {}
    options = []

    for idx, col in enumerate(df.columns.tolist()):
        seen[col] = seen.get(col, 0) + 1
        label = col if seen[col] == 1 else f"{col} ({seen[col]})"
        options.append({"label": label, "index": idx, "name": col})

    return options


def get_numeric_column_options(df):
    return [
        option
        for option in build_column_options(df)
        if pd.api.types.is_numeric_dtype(df.iloc[:, option["index"]])
    ]


def get_categorical_column_options(df):
    return [
        option
        for option in build_column_options(df)
        if pd.api.types.is_object_dtype(df.iloc[:, option["index"]])
        or pd.api.types.is_string_dtype(df.iloc[:, option["index"]])
    ]


def can_render_chart(df):
    if df.empty or len(df) < 2:
        return False

    numeric_options = get_numeric_column_options(df)
    categorical_options = get_categorical_column_options(df)
    return bool(categorical_options and numeric_options)


def explain_result(client, question, df):
    sample = df.head(5).to_string()
    prompt = f"""
Explain this SQL result in simple terms.

Question:
{question}

Sample:
{sample}
"""
    result = stream_text_with_telemetry(prompt, model=DEFAULT_SQL_MODEL, temperature=0.2)
    return result.get("text", "")


def build_insight_prompt(question, df):
    sample = df.head(5).to_string()
    semantic_block = semantic_prompt_block(st.session_state.get("semantic_context"))
    conversation_block = memory_prompt_block(st.session_state.get("analytics_memory"))
    autonomous_block = insight_prompt_block(st.session_state.get("autonomous_insights"))
    investigation_block = investigation_prompt_block(st.session_state.get("investigation_state"))
    scheduled_briefing_block = briefing_prompt_block(st.session_state.get("executive_briefing"))
    return f"""
Explain this SQL result in simple business terms for an analytics operator.

Question:
{question}

Sample:
{sample}
{semantic_block}
{conversation_block}
{autonomous_block}
{investigation_block}
{scheduled_briefing_block}

Write an executive-style insight brief. Prioritize critical or warning findings when present, and keep it concise and actionable.
"""


def stream_insight_narration(question, df, sql="", live_placeholder=None):
    stream = st.session_state.streaming_workflow
    base_trace = enrich_trace_with_telemetry(
        st.session_state.workflow_trace,
        st.session_state.workflow_telemetry,
    )
    stream["current_phase"] = "autonomous insight"
    stream["trace"] = base_trace + [
        {
            "step": "autonomous insight",
            "status": "active",
            "detail": "Scanning result set for autonomous insights.",
            "timestamp": current_timestamp(),
            "phase": "autonomous insight",
        }
    ]
    st.session_state.streaming_workflow = stream
    append_live_log("autonomous insight", "Scanning result set for trends, anomalies, and concentration.", status="active")
    st.session_state.autonomous_insights = analyze_result_set(df, question)
    insight_severity = st.session_state.autonomous_insights.get("severity", "info")
    scan_completed_at = current_timestamp()
    stream = st.session_state.streaming_workflow
    stream["trace"] = base_trace + [
        {
            "step": "autonomous insight",
            "status": "success",
            "detail": f"Insight scan completed with {insight_severity} severity.",
            "timestamp": scan_completed_at,
            "phase": "autonomous insight",
            "severity": insight_severity,
        },
    ]
    stream["current_phase"] = "autonomous insight"
    stream.setdefault("assistant_streams", {})["autonomous insight"] = insight_prompt_block(
        st.session_state.autonomous_insights
    ).strip()
    st.session_state.streaming_workflow = stream
    sync_live_state_from_stream()
    if live_placeholder is not None:
        render_live_workspace_snapshot(question, live_placeholder)
    append_live_log(
        "autonomous insight",
        f'Insight scan completed with {st.session_state.autonomous_insights.get("severity", "info")} severity.',
    )
    investigation_base_trace = stream["trace"]
    post_investigation_trace = run_autonomous_investigation_phase(
        question,
        sql,
        investigation_base_trace,
        live_placeholder=live_placeholder,
    )
    insight_started_at = current_timestamp()
    stream = st.session_state.streaming_workflow
    stream["current_phase"] = "insight"
    stream["trace"] = post_investigation_trace + [
        {
            "step": "insight",
            "status": "active",
            "detail": "Narrating executive insight brief.",
            "timestamp": insight_started_at,
            "phase": "insight",
        }
    ]
    st.session_state.streaming_workflow = stream
    append_live_log("insight", "Narrating executive insight brief.", status="active")

    def on_token(token, accumulated):
        stream = st.session_state.streaming_workflow
        stream.setdefault("assistant_streams", {})["insight"] = accumulated
        stream["updated_at"] = current_timestamp()
        st.session_state.streaming_workflow = stream
        sync_live_state_from_stream()
        if live_placeholder is not None:
            now = time.perf_counter()
            if now - st.session_state.last_stream_render >= 0.08:
                st.session_state.last_stream_render = now
                st.session_state.live_render_seq += 1
                render_live_workspace_snapshot(question, live_placeholder)

    result = stream_text_with_telemetry(
        build_insight_prompt(question, df),
        model=DEFAULT_SQL_MODEL,
        temperature=0.2,
        token_callback=on_token,
    )
    insight = (result.get("text") or "").strip()
    telemetry = result.get("telemetry", {})
    st.session_state.latest_insight = "" if insight.startswith("ERROR:") else insight
    if telemetry:
        workflow_telemetry = dict(st.session_state.workflow_telemetry or {})
        steps = list(workflow_telemetry.get("steps", []))
        steps.append({"step": "insight", **telemetry})
        latest_error = latest_telemetry_error(steps)
        workflow_telemetry.update(
            {
                "steps": steps,
                "prompt_tokens": sum(item.get("prompt_tokens", 0) for item in steps),
                "completion_tokens": sum(item.get("completion_tokens", 0) for item in steps),
                "total_tokens": sum(item.get("total_tokens", 0) for item in steps),
                "cost_usd": sum(item.get("cost_usd", 0.0) for item in steps),
                "latency_ms": sum(item.get("latency_ms", 0) for item in steps),
                "model": telemetry.get("model") or workflow_telemetry.get("model", ""),
                "usage_available": any(item.get("usage_available", False) for item in steps),
                "error_type": latest_error.get("error_type"),
                "error_message": latest_error.get("error_message"),
                "error_details": latest_error.get("error_details"),
            }
        )
        st.session_state.workflow_telemetry = workflow_telemetry
        stream = st.session_state.streaming_workflow
        stream["telemetry"] = workflow_telemetry
        st.session_state.streaming_workflow = stream

    if insight.startswith("ERROR:"):
        append_live_log("insight", insight, status="warning")
    else:
        stream = st.session_state.streaming_workflow
        completed_at = current_timestamp()
        trace_without_active = [
            item
            for item in stream.get("trace", [])
            if not (item.get("step") == "insight" and item.get("status") == "active")
        ]
        stream["trace"] = trace_without_active + [
            {
                "step": "insight",
                "status": "success",
                "detail": "Executive insight brief completed.",
                "timestamp": completed_at,
                "phase": "insight",
                "severity": insight_severity,
            }
        ]
        stream.setdefault("assistant_streams", {})["insight"] = insight
        st.session_state.streaming_workflow = stream
        append_live_log("insight", "Insight narration completed.")

    sync_live_state_from_stream()
    if live_placeholder is not None:
        st.session_state.live_render_seq += 1
        render_live_workspace_snapshot(question, live_placeholder)
    return st.session_state.latest_insight


def build_ai_recommendations(df, telemetry, trace):
    recommendations = []
    context = st.session_state.get("semantic_context", {})
    memory = st.session_state.get("analytics_memory", {})
    insight_state = st.session_state.get("autonomous_insights", {})
    investigation_state = st.session_state.get("investigation_state", {})
    if insight_state.get("severity") in {"warning", "critical"} and insight_state.get("findings"):
        top_finding = insight_state["findings"][0]
        recommendations.append(f"Prioritize the {top_finding.get('type', 'signal')} finding: {top_finding.get('title', '')}.")
    if investigation_state.get("status") == "completed":
        recommendations.append("Review the drill-down investigation summary before deciding whether to refine the query further.")
    if context.get("metrics") and context.get("time_columns"):
        recommendations.append("Trend the primary metric over the detected time field to identify momentum changes.")
    if context.get("categorical_fields") and context.get("metrics"):
        recommendations.append("Segment the leading metric by a categorical field to find concentration or outliers.")
    if memory.get("previous_dimensions") and memory.get("previous_metrics"):
        recommendations.append("Ask a focused follow-up by filtering the previous dimension or changing the chart type.")
    if not df.empty and len(df.columns) >= 2:
        recommendations.append("Compare the leading dimension against a secondary metric to identify outliers or concentration risk.")
    if len(df) > 20:
        recommendations.append("Apply a tighter categorical filter or ranking slice to surface the most decision-relevant cohort.")
    if telemetry and telemetry.get("latency_ms", 0) > 0:
        recommendations.append(f"Latest workflow latency was {telemetry.get('latency_ms')} ms; monitor this pattern if prompt complexity increases.")
    if trace:
        last_step = trace[-1].get("step", "execution")
        recommendations.append(f"The orchestration completed through {last_step}; inspect that step first when validating future regressions.")
    return recommendations[:4]


def build_default_activity_feed():
    return [
        {"title": "Copilot standby initialized", "subtitle": "Natural-language query intake is ready for the next request.", "time": "Now", "tone": "live"},
        {"title": "Schema context cached", "subtitle": "Database structure is warm for low-latency retrieval.", "time": "2m", "tone": "stable"},
        {"title": "Telemetry observers connected", "subtitle": "Token, latency, and cost tracking are listening for the next run.", "time": "5m", "tone": "stable"},
        {"title": "Recommendation engine primed", "subtitle": "Default guidance prepared from recent workflow patterns.", "time": "9m", "tone": "live"},
    ]


def build_default_agent_states():
    return [
        {"name": "Planner", "status": "Ready", "caption": "Intent routing active.", "active": True},
        {"name": "Schema", "status": "Warm", "caption": "Context cache hydrated.", "active": False},
        {"name": "Memory", "status": "Listening", "caption": "History retrieval on standby.", "active": False},
        {"name": "SQL Agent", "status": "Idle", "caption": "Generation lane available.", "active": False},
    ]


def init_session_state():
    defaults = {
        "workflow_trace": [],
        "workflow_telemetry": {},
        "messages": [],
        "history": [],
        "latest_df": None,
        "latest_sql": "",
        "latest_question": "",
        "latest_exec_time": None,
        "latest_insight": "",
        "latest_mode": "database",
        "uploaded_name": None,
        "command_text": "",
        "run_id": "default",
        "run_counter": 0,
        "live_render_seq": 0,
        "plotly_key_seq": 0,
        "live_trace": [],
        "live_logs": [],
        "live_telemetry": {},
        "live_assistant_streams": {},
        "streaming_workflow": {},
        "semantic_context": {},
        "semantic_memory": {},
        "analytics_memory": empty_analytics_memory(),
        "autonomous_insights": empty_insight_state(),
        "investigation_state": empty_investigation_state(),
        "monitoring_config": default_monitoring_config(),
        "monitoring_state": empty_monitoring_state(),
        "executive_briefing": empty_briefing_state(),
        "monitoring_runs": [],
        "pending_monitoring_run": False,
        "user_identity": default_user_session(),
        "workspace_memory": default_workspace_memory(default_user_session()),
        "workspace_loaded": False,
        "workspace_session_id": "",
        "latest_execution_graph": {},
        "latest_stage_confidence": {},
        "latest_recovery": {},
        "latest_policy_decision": {},
        "active_intent": "",
        "workspace_route": "Overview",
        "last_stream_render": 0.0,
        "is_executing": False,
        "x_col": None,
        "y_col": None,
        "chart_type": "Bar",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def clear_session():
    st.session_state.messages = []
    st.session_state.history = []
    st.session_state.workflow_trace = []
    st.session_state.workflow_telemetry = {}
    st.session_state.latest_df = None
    st.session_state.latest_sql = ""
    st.session_state.latest_question = ""
    st.session_state.latest_exec_time = None
    st.session_state.latest_insight = ""
    st.session_state.latest_mode = "database"
    st.session_state.uploaded_name = None
    st.session_state.command_text = ""
    st.session_state.run_id = "default"
    st.session_state.run_counter = 0
    st.session_state.live_render_seq = 0
    st.session_state.plotly_key_seq = 0
    st.session_state.live_trace = []
    st.session_state.live_logs = []
    st.session_state.live_telemetry = {}
    st.session_state.live_assistant_streams = {}
    st.session_state.streaming_workflow = {}
    st.session_state.semantic_context = {}
    st.session_state.semantic_memory = {}
    st.session_state.analytics_memory = empty_analytics_memory()
    st.session_state.autonomous_insights = empty_insight_state()
    st.session_state.investigation_state = empty_investigation_state()
    st.session_state.monitoring_config = default_monitoring_config()
    st.session_state.monitoring_state = empty_monitoring_state()
    st.session_state.executive_briefing = empty_briefing_state()
    st.session_state.monitoring_runs = []
    st.session_state.pending_monitoring_run = False
    st.session_state.workspace_memory = default_workspace_memory(st.session_state.get("user_identity", default_user_session()))
    st.session_state.workspace_loaded = False
    st.session_state.latest_execution_graph = {}
    st.session_state.latest_stage_confidence = {}
    st.session_state.latest_recovery = {}
    st.session_state.latest_policy_decision = {}
    st.session_state.active_intent = ""
    st.session_state.last_stream_render = 0.0
    st.session_state.is_executing = False
    st.session_state.x_col = None
    st.session_state.y_col = None
    st.session_state.chart_type = "Bar"
    if "uploaded_df" in st.session_state:
        del st.session_state["uploaded_df"]


def current_timestamp():
    return datetime.now().isoformat(timespec="seconds")


def configure_workspace_session(user_id, team_id, role):
    identity = build_user_session(user_id, team_id, role)
    previous_workspace = st.session_state.get("user_identity", {}).get("workspace_id")
    st.session_state.user_identity = identity
    if not st.session_state.get("workspace_loaded") or previous_workspace != identity["workspace_id"]:
        memory = load_workspace_memory(identity)
        session = start_workspace_session(memory)
        st.session_state.workspace_memory = memory
        st.session_state.workspace_session_id = session["session_id"]
        st.session_state.workspace_loaded = True
        st.session_state.history = list(memory.get("query_history", []))[-10:]
        st.session_state.semantic_memory = dict(memory.get("semantic_dataset_memory", {}))
        if st.session_state.semantic_memory and not st.session_state.get("semantic_context"):
            st.session_state.semantic_context = next(reversed(st.session_state.semantic_memory.values()))


def persist_workspace_memory():
    identity = st.session_state.get("user_identity", default_user_session())
    st.session_state.workspace_memory = save_workspace_memory(identity, st.session_state.get("workspace_memory", {}))


def persist_workspace_snapshot(question, intent, sql, df):
    memory = snapshot_workspace_run(
        st.session_state.get("workspace_memory", default_workspace_memory(st.session_state.get("user_identity"))),
        question=question,
        intent=intent,
        sql=sql,
        rows=len(df) if df is not None and not df.empty else 0,
        workflow_trace=st.session_state.get("workflow_trace", []),
        telemetry=st.session_state.get("workflow_telemetry", {}),
        insights=st.session_state.get("autonomous_insights", {}),
        investigation=st.session_state.get("investigation_state", {}),
        semantic_memory=st.session_state.get("semantic_memory", {}),
    )
    st.session_state.workspace_memory = memory
    persist_workspace_memory()


def persist_investigation_bookmark(note="Operator bookmark"):
    memory = bookmark_investigation(
        st.session_state.get("workspace_memory", {}),
        st.session_state.get("investigation_state", {}),
        note=note,
    )
    st.session_state.workspace_memory = memory
    persist_workspace_memory()


def display_timestamp(value=None):
    raw_value = value or current_timestamp()
    try:
        return datetime.fromisoformat(raw_value).strftime("%H:%M:%S")
    except ValueError:
        return time.strftime("%H:%M:%S")


def initial_streaming_workflow(question):
    started_at = current_timestamp()
    return {
        "question": question,
        "run_id": st.session_state.run_id,
        "status": "running",
        "current_phase": "planner",
        "started_at": started_at,
        "updated_at": started_at,
        "completed_at": None,
        "events": [],
        "trace": [],
        "assistant_streams": {},
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


def store_semantic_context(key, context):
    if not context:
        return
    st.session_state.semantic_context = context
    memory = dict(st.session_state.get("semantic_memory", {}))
    memory[key] = context
    st.session_state.semantic_memory = memory


def ensure_schema_semantics():
    memory = st.session_state.get("semantic_memory", {})
    if "sql_schema" not in memory:
        store_semantic_context("sql_schema", profile_schema(get_schema(), name="Chinook SQL schema"))
    return st.session_state.semantic_memory["sql_schema"]


def profile_active_dataframe(df, name):
    context = profile_dataframe(df, name=name)
    store_semantic_context(name, context)
    return context


def apply_chart_followup(question):
    followup = contextualize_followup(question, st.session_state.get("analytics_memory"))
    chart_type = followup.get("chart_type")
    if chart_type:
        st.session_state.chart_type = chart_type
    return followup


def current_chart_state():
    return {
        "x_col": st.session_state.get("x_col"),
        "y_col": st.session_state.get("y_col"),
        "chart_type": st.session_state.get("chart_type"),
    }


def remember_analytics_turn(question, effective_question, sql, df):
    st.session_state.analytics_memory = update_analytics_memory(
        st.session_state.get("analytics_memory"),
        question=question,
        effective_question=effective_question,
        sql=sql,
        df=df,
        semantic_context=st.session_state.get("semantic_context"),
        chart_state=current_chart_state(),
    )


def complete_chart_only_followup(question, followup):
    st.session_state.messages.append({"role": "user", "content": question})
    st.session_state.latest_question = question
    st.session_state.active_intent = followup.get("effective_question", question)
    st.session_state.streaming_workflow = initial_streaming_workflow(question)
    append_live_log("planner", "Applied follow-up request to the existing visualization context.")
    completed_at = current_timestamp()
    stream = st.session_state.streaming_workflow
    stream["status"] = "completed"
    stream["completed_at"] = completed_at
    stream["updated_at"] = completed_at
    st.session_state.streaming_workflow = stream
    sync_live_state_from_stream()
    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": f"Updated the current visualization to {st.session_state.chart_type.lower()} chart mode.",
        }
    )
    remember_analytics_turn(
        question,
        followup.get("effective_question", question),
        st.session_state.get("latest_sql", ""),
        st.session_state.get("latest_df"),
    )


def enrich_trace_with_telemetry(trace, telemetry):
    telemetry_steps = {item.get("step"): item for item in telemetry.get("steps", [])} if telemetry else {}
    enriched = []
    for item in trace:
        combined = dict(item)
        step_meta = telemetry_steps.get(item.get("step"), {})
        for key in (
            "model",
            "latency_ms",
            "prompt_tokens",
            "completion_tokens",
            "total_tokens",
            "cost_usd",
            "error_type",
            "error_message",
        ):
            if key in step_meta:
                combined[key] = step_meta.get(key)
        enriched.append(combined)
    return enriched


def latest_telemetry_error(steps):
    return next((item for item in reversed(steps) if item.get("error_type") or item.get("error_message")), {})


def sync_live_state_from_stream():
    stream = st.session_state.streaming_workflow or {}
    st.session_state.live_trace = enrich_trace_with_telemetry(
        stream.get("trace", []),
        stream.get("telemetry", {}),
    )
    st.session_state.live_logs = [
        {
            "time": display_timestamp(event.get("timestamp")),
            "step": event.get("step") or event.get("phase") or "system",
            "message": event.get("detail") or "",
        }
        for event in stream.get("events", [])
    ]
    st.session_state.live_telemetry = stream.get("telemetry", {})
    st.session_state.live_assistant_streams = stream.get("assistant_streams", {})


def persist_streaming_event(phase, state_snapshot, step, detail):
    stream = st.session_state.streaming_workflow or initial_streaming_workflow(
        st.session_state.get("latest_question") or st.session_state.get("command_text") or ""
    )
    event = dict(state_snapshot.get("event", {}))
    timestamp = event.get("timestamp") or current_timestamp()
    status = event.get("status") or phase
    event.update(
        {
            "phase": event.get("phase") or step,
            "status": status,
            "step": step,
            "detail": detail,
            "timestamp": timestamp,
        }
    )

    if status == "streaming":
        stream.setdefault("assistant_streams", {})[step] = event.get("content", "")
        stream["telemetry"] = event.get("telemetry") or state_snapshot.get("telemetry") or stream.get("telemetry") or {}
        stream["current_phase"] = step
        stream["updated_at"] = timestamp
        events = stream.setdefault("events", [])
        streaming_detail = f"Streaming {step} tokens..."
        if events and events[-1].get("status") == "streaming" and events[-1].get("step") == step:
            events[-1].update({**event, "detail": streaming_detail})
        else:
            events.append({**event, "detail": streaming_detail})
        st.session_state.streaming_workflow = stream
        sync_live_state_from_stream()
        return

    stream["status"] = "running" if status == "active" else stream.get("status", "running")
    stream["current_phase"] = step
    stream["updated_at"] = timestamp
    stream.setdefault("events", []).append(event)
    if state_snapshot.get("telemetry_event"):
        stream.setdefault("telemetry_events", []).append(state_snapshot["telemetry_event"])

    telemetry = state_snapshot.get("telemetry") or stream.get("telemetry") or {}
    stream["telemetry"] = telemetry

    trace = enrich_trace_with_telemetry(state_snapshot.get("trace", []), telemetry)
    if status == "active":
        active_item = {
            "step": step,
            "status": "active",
            "detail": detail,
            "timestamp": timestamp,
            "phase": step,
        }
        trace = trace + [active_item]
    stream["trace"] = trace

    st.session_state.streaming_workflow = stream
    sync_live_state_from_stream()


def append_live_log(step, message, timestamp=None, status="completed"):
    event = {
        "phase": step,
        "status": status,
        "step": step,
        "detail": message,
        "timestamp": timestamp or current_timestamp(),
    }
    stream = st.session_state.streaming_workflow or initial_streaming_workflow(
        st.session_state.get("latest_question") or st.session_state.get("command_text") or ""
    )
    stream.setdefault("events", []).append(event)
    stream["updated_at"] = event["timestamp"]
    st.session_state.streaming_workflow = stream
    sync_live_state_from_stream()


def merge_investigation_telemetry(investigation_state):
    investigation_telemetry = (investigation_state or {}).get("telemetry", {})
    if not investigation_telemetry:
        return
    workflow_telemetry = dict(st.session_state.workflow_telemetry or {})
    steps = list(workflow_telemetry.get("steps", [])) + list(investigation_telemetry.get("steps", []))
    latest_error = latest_telemetry_error(steps)
    workflow_telemetry.update(
        {
            "steps": steps,
            "prompt_tokens": sum(item.get("prompt_tokens", 0) for item in steps),
            "completion_tokens": sum(item.get("completion_tokens", 0) for item in steps),
            "total_tokens": sum(item.get("total_tokens", 0) for item in steps),
            "cost_usd": sum(item.get("cost_usd", 0.0) for item in steps),
            "latency_ms": sum(item.get("latency_ms", 0) for item in steps),
            "model": investigation_telemetry.get("model") or workflow_telemetry.get("model", ""),
            "usage_available": any(item.get("usage_available", False) for item in steps),
            "error_type": latest_error.get("error_type"),
            "error_message": latest_error.get("error_message"),
            "error_details": latest_error.get("error_details"),
        }
    )
    st.session_state.workflow_telemetry = workflow_telemetry
    stream = st.session_state.streaming_workflow
    stream["telemetry"] = workflow_telemetry
    st.session_state.streaming_workflow = stream


def merge_monitoring_telemetry(monitoring_state):
    monitoring_telemetry = (monitoring_state or {}).get("telemetry", {})
    if not monitoring_telemetry:
        return
    workflow_telemetry = dict(st.session_state.workflow_telemetry or {})
    steps = list(workflow_telemetry.get("steps", [])) + list(monitoring_telemetry.get("steps", []))
    latest_error = latest_telemetry_error(steps)
    workflow_telemetry.update(
        {
            "steps": steps,
            "prompt_tokens": sum(item.get("prompt_tokens", 0) for item in steps),
            "completion_tokens": sum(item.get("completion_tokens", 0) for item in steps),
            "total_tokens": sum(item.get("total_tokens", 0) for item in steps),
            "cost_usd": sum(item.get("cost_usd", 0.0) for item in steps),
            "latency_ms": sum(item.get("latency_ms", 0) for item in steps),
            "model": monitoring_telemetry.get("model") or workflow_telemetry.get("model", ""),
            "usage_available": any(item.get("usage_available", False) for item in steps),
            "error_type": latest_error.get("error_type"),
            "error_message": latest_error.get("error_message"),
            "error_details": latest_error.get("error_details"),
        }
    )
    st.session_state.workflow_telemetry = workflow_telemetry
    stream = st.session_state.streaming_workflow
    stream["telemetry"] = workflow_telemetry
    st.session_state.streaming_workflow = stream


def briefing_prompt_block(briefing_state):
    if not briefing_state or briefing_state.get("status") == "idle":
        return ""
    sections = briefing_state.get("sections", [])
    section_text = "\n".join(
        f"- [{item.get('severity', 'info')}] {item.get('target', '')}: {item.get('trend', '')}; {item.get('investigation', '')}"
        for item in sections
    )
    return (
        "\n\nScheduled executive briefing:\n"
        f"{briefing_state.get('summary', '')}\n"
        f"{section_text or '- No briefing sections'}"
    )


def run_monitoring_workflow(live_placeholder=None):
    config = st.session_state.get("monitoring_config", default_monitoring_config())
    targets = config.get("targets") or []
    if not targets:
        st.warning("Select at least one monitoring target.")
        return
    if not user_can(st.session_state.get("user_identity"), "monitor"):
        st.warning("Your current workspace role does not allow scheduled monitoring.")
        return

    st.session_state.run_counter += 1
    st.session_state.run_id = f"monitor_{st.session_state.run_counter}"
    question = f"Scheduled monitoring: {', '.join(targets)}"
    st.session_state.latest_question = question
    st.session_state.latest_mode = "monitoring"
    st.session_state.latest_insight = ""
    st.session_state.streaming_workflow = initial_streaming_workflow(question)
    st.session_state.live_trace = []
    st.session_state.live_logs = []
    st.session_state.live_telemetry = {}
    st.session_state.live_assistant_streams = {}
    st.session_state.workflow_trace = []
    st.session_state.workflow_telemetry = {}
    sync_live_state_from_stream()
    append_live_log("monitoring", "Scheduled monitoring workflow started.", status="active")

    started_at = current_timestamp()
    stream = st.session_state.streaming_workflow
    stream["current_phase"] = "monitoring"
    stream["trace"] = [
        {
            "step": "monitoring",
            "status": "active",
            "detail": "Running scheduled KPI checks.",
            "timestamp": started_at,
            "phase": "monitoring",
        }
    ]
    st.session_state.streaming_workflow = stream
    if live_placeholder is not None:
        render_live_workspace_snapshot(question, live_placeholder)

    def on_monitoring_event(status, step, detail):
        append_live_log(step, detail, status=status)
        stream = st.session_state.streaming_workflow
        stream.setdefault("assistant_streams", {})[step] = detail
        stream["updated_at"] = current_timestamp()
        st.session_state.streaming_workflow = stream
        sync_live_state_from_stream()
        if live_placeholder is not None:
            render_live_workspace_snapshot(question, live_placeholder)

    monitoring_state, briefing = run_monitoring_checks(
        targets,
        st.session_state.get("semantic_context"),
        callback=on_monitoring_event,
    )
    st.session_state.monitoring_state = monitoring_state
    st.session_state.executive_briefing = briefing
    merge_monitoring_telemetry(monitoring_state)

    completed_at = current_timestamp()
    trace = [
        {
            "step": "monitoring",
            "status": "success",
            "detail": monitoring_state.get("summary", "Monitoring completed."),
            "timestamp": completed_at,
            "phase": "monitoring",
            "severity": monitoring_state.get("severity", "info"),
        },
        {
            "step": "autonomous insight",
            "status": "success",
            "detail": "Monitoring targets scanned for anomalies and trends.",
            "timestamp": completed_at,
            "phase": "autonomous insight",
            "severity": monitoring_state.get("severity", "info"),
        },
        {
            "step": "investigation",
            "status": "success"
            if any((check.get("investigation") or {}).get("status") == "completed" for check in monitoring_state.get("checks", []))
            else "skipped",
            "detail": "Autonomous investigations completed for eligible monitoring signals.",
            "timestamp": completed_at,
            "phase": "investigation",
        },
        {
            "step": "briefing",
            "status": "success",
            "detail": briefing.get("summary", "Executive briefing generated."),
            "timestamp": completed_at,
            "phase": "briefing",
            "severity": briefing.get("severity", "info"),
        },
    ]
    stream = st.session_state.streaming_workflow
    stream["trace"] = trace
    stream["status"] = "completed"
    stream["completed_at"] = completed_at
    stream["updated_at"] = completed_at
    stream.setdefault("assistant_streams", {})["briefing"] = briefing_prompt_block(briefing)
    st.session_state.streaming_workflow = stream
    sync_live_state_from_stream()
    st.session_state.workflow_trace = st.session_state.live_trace
    st.session_state.workflow_telemetry = st.session_state.live_telemetry
    st.session_state.monitoring_config = {**config, "last_run_at": completed_at}
    st.session_state.monitoring_runs = (
        st.session_state.get("monitoring_runs", [])
        + [
            {
                "time": completed_at,
                "targets": targets,
                "severity": monitoring_state.get("severity", "info"),
                "summary": briefing.get("summary", ""),
            }
        ]
    )[-10:]
    st.session_state.history.append(
        {
            "question": question,
            "intent": "Scheduled KPI monitoring and executive briefing",
            "sql": "Scheduled monitoring targets",
            "rows": sum(check.get("row_count", 0) for check in monitoring_state.get("checks", [])),
        }
    )
    memory = st.session_state.get("workspace_memory", default_workspace_memory(st.session_state.get("user_identity")))
    memory = snapshot_workspace_run(
        memory,
        question=question,
        intent="Scheduled KPI monitoring and executive briefing",
        sql="Scheduled monitoring targets",
        rows=sum(check.get("row_count", 0) for check in monitoring_state.get("checks", [])),
        workflow_trace=st.session_state.get("workflow_trace", []),
        telemetry=st.session_state.get("workflow_telemetry", {}),
        insights={"findings": [section for section in briefing.get("sections", [])], "severity": briefing.get("severity", "info")},
        investigation={"status": "completed", "summary": "Monitoring investigations persisted with briefing.", "queries": []},
        semantic_memory=st.session_state.get("semantic_memory", {}),
    )
    st.session_state.workspace_memory = memory
    persist_workspace_memory()
    append_live_log("briefing", briefing.get("summary", "Executive briefing generated."))
    if live_placeholder is not None:
        render_live_workspace_snapshot(question, live_placeholder)


def run_autonomous_investigation_phase(question, sql, base_trace, live_placeholder=None):
    if not sql or st.session_state.get("latest_mode") == "csv" or not should_investigate(st.session_state.autonomous_insights):
        skipped_at = current_timestamp()
        st.session_state.investigation_state = {
            **empty_investigation_state(),
            "status": "skipped",
            "summary": "Investigation skipped because this run has no database-backed warning or critical signal.",
        }
        skipped_trace = base_trace + [
            {
                "step": "investigation",
                "status": "skipped",
                "detail": st.session_state.investigation_state["summary"],
                "timestamp": skipped_at,
                "phase": "investigation",
            }
        ]
        stream = st.session_state.streaming_workflow
        stream["trace"] = skipped_trace
        st.session_state.streaming_workflow = stream
        append_live_log("investigation", st.session_state.investigation_state["summary"], status="skipped")
        return skipped_trace

    started_at = current_timestamp()
    stream = st.session_state.streaming_workflow
    stream["current_phase"] = "investigation"
    stream["trace"] = base_trace + [
        {
            "step": "investigation",
            "status": "active",
            "detail": "Generating autonomous drill-down queries.",
            "timestamp": started_at,
            "phase": "investigation",
        }
    ]
    st.session_state.streaming_workflow = stream
    append_live_log("investigation", "Starting autonomous root-cause investigation.", status="active")

    def on_investigation_event(status, step, detail):
        append_live_log(step, detail, status=status)
        stream = st.session_state.streaming_workflow
        stream.setdefault("assistant_streams", {})["investigation"] = detail
        stream["updated_at"] = current_timestamp()
        st.session_state.streaming_workflow = stream
        sync_live_state_from_stream()
        if live_placeholder is not None:
            render_live_workspace_snapshot(question, live_placeholder)

    investigation_state = run_investigation(
        question,
        sql,
        st.session_state.autonomous_insights,
        st.session_state.get("semantic_context"),
        max_queries=3,
        callback=on_investigation_event,
    )
    st.session_state.investigation_state = investigation_state
    merge_investigation_telemetry(investigation_state)
    completed_at = current_timestamp()
    status = "success" if investigation_state.get("status") == "completed" else "warning"
    completed_trace = base_trace + [
        {
            "step": "investigation",
            "status": status,
            "detail": investigation_state.get("summary", "Investigation finished."),
            "timestamp": completed_at,
            "phase": "investigation",
            "severity": investigation_state.get("severity", "info"),
        }
    ]
    stream = st.session_state.streaming_workflow
    stream["trace"] = completed_trace
    stream.setdefault("assistant_streams", {})["investigation"] = investigation_prompt_block(investigation_state).strip()
    st.session_state.streaming_workflow = stream
    append_live_log("investigation", investigation_state.get("summary", "Investigation finished."), status=status)
    if live_placeholder is not None:
        render_live_workspace_snapshot(question, live_placeholder)
    return completed_trace


def render_live_workspace_snapshot(question, placeholder):
    sync_live_state_from_stream()
    with placeholder.container():
        render_live_execution_panel(
            question,
            st.session_state.live_trace,
            st.session_state.live_logs,
            st.session_state.live_telemetry,
            chart_key=next_plotly_key("workflow_chart_live"),
            assistant_streams=st.session_state.live_assistant_streams,
        )


def run_query(question, live_placeholder=None):
    if not user_can(st.session_state.get("user_identity"), "query"):
        st.warning("Your current workspace role does not allow query execution.")
        return
    followup = apply_chart_followup(question)
    if st.session_state.get("latest_df") is not None and is_chart_only_followup(question, st.session_state.get("analytics_memory")):
        complete_chart_only_followup(question, followup)
        return

    st.session_state.messages.append({"role": "user", "content": question})
    start = time.time()
    sql = ""
    workflow_result = None
    st.session_state.run_counter += 1
    st.session_state.run_id = f"run_{st.session_state.run_counter}"
    st.session_state.live_render_seq = 0
    st.session_state.is_executing = True
    st.session_state.latest_question = question
    st.session_state.active_intent = followup.get("effective_question", question)
    st.session_state.latest_insight = ""
    st.session_state.autonomous_insights = empty_insight_state()
    st.session_state.investigation_state = empty_investigation_state()
    st.session_state.streaming_workflow = initial_streaming_workflow(question)
    st.session_state.live_trace = []
    st.session_state.live_logs = []
    st.session_state.live_telemetry = {}
    st.session_state.live_assistant_streams = {}
    sync_live_state_from_stream()

    def workflow_callback(phase, state_snapshot, step, detail):
        persist_streaming_event(phase, state_snapshot, step, detail)
        if live_placeholder is not None:
            now = time.perf_counter()
            if phase == "streaming" and now - st.session_state.last_stream_render < 0.08:
                return
            st.session_state.last_stream_render = now
            st.session_state.live_render_seq += 1
            render_live_workspace_snapshot(question, live_placeholder)

    try:
        if "uploaded_df" in st.session_state:
            df = st.session_state.uploaded_df
            profile_active_dataframe(df, f"Uploaded CSV: {st.session_state.get('uploaded_name') or 'dataset'}")
            st.session_state.workflow_trace = []
            st.session_state.workflow_telemetry = {}
            mode = "csv"
            append_live_log("schema retrieval", "Uploaded CSV loaded into the analytics workspace.")
            if live_placeholder is not None:
                render_live_workspace_snapshot(question, live_placeholder)
        else:
            if live_placeholder is not None:
                render_live_workspace_snapshot(question, live_placeholder)

            schema_context = ensure_schema_semantics()
            workflow_context = {
                **schema_context,
                "prompt_block": semantic_prompt_block(schema_context),
            }
            workflow_result = execute_query_workflow(
                question,
                callback=workflow_callback,
                semantic_context=workflow_context,
                conversation_context=st.session_state.get("analytics_memory"),
                workspace_context=st.session_state.get("workspace_memory"),
            )
            st.session_state.active_intent = workflow_result.get("effective_question") or st.session_state.active_intent
            st.session_state.workflow_trace = workflow_result.get("trace", [])
            st.session_state.workflow_telemetry = validate_telemetry_payload(workflow_result.get("telemetry", {}))
            st.session_state.latest_execution_graph = workflow_result.get("execution_graph", {})
            st.session_state.latest_stage_confidence = workflow_result.get("stage_confidence", {})
            st.session_state.latest_recovery = workflow_result.get("recovery", {})
            st.session_state.latest_policy_decision = workflow_result.get("policy_decision", {})
            sql = (workflow_result.get("sql") or "").strip()
            workflow_error = workflow_result.get("error")

            if workflow_error:
                st.error(workflow_error)
                append_live_log("system", workflow_error, status="error")
                stream = st.session_state.streaming_workflow
                failed_at = current_timestamp()
                stream["status"] = "failed"
                stream["completed_at"] = failed_at
                stream["updated_at"] = failed_at
                st.session_state.streaming_workflow = stream
                sync_live_state_from_stream()
                if live_placeholder is not None:
                    render_live_workspace_snapshot(question, live_placeholder)
                if sql:
                    st.code(sql, language="sql")
                return

            cols = workflow_result.get("columns", [])
            rows = workflow_result.get("rows", [])
            if not cols:
                st.warning("No columns returned or query failed.")
                append_live_log("system", "No columns returned or query failed.", status="warning")
                if live_placeholder is not None:
                    render_live_workspace_snapshot(question, live_placeholder)
                return
            df = pd.DataFrame(rows, columns=cols)
            profile_active_dataframe(df, f"SQL result: {question[:48]}")
            mode = "database"

        exec_time = time.time() - start
        st.session_state.latest_df = df
        st.session_state.latest_sql = sql
        st.session_state.latest_question = question
        st.session_state.latest_exec_time = exec_time
        st.session_state.latest_mode = mode
        stream_insight_narration(question, df, sql=sql, live_placeholder=live_placeholder)
        remember_analytics_turn(question, st.session_state.get("active_intent") or question, sql, df)
        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": st.session_state.latest_insight
                or f"Query executed successfully. Returned {len(df)} rows.",
            }
        )
        append_live_log("system", f"Workflow completed successfully in {exec_time:.2f}s.")
        stream = st.session_state.streaming_workflow
        completed_at = current_timestamp()
        stream["status"] = "completed"
        stream["completed_at"] = completed_at
        stream["updated_at"] = completed_at
        st.session_state.streaming_workflow = stream
        sync_live_state_from_stream()
        st.session_state.workflow_trace = st.session_state.live_trace
        st.session_state.workflow_telemetry = st.session_state.live_telemetry
        if live_placeholder is not None:
            render_live_workspace_snapshot(question, live_placeholder)
        st.session_state.history.append(
            {
                "question": question,
                "intent": st.session_state.get("active_intent") or question,
                "sql": sql,
                "rows": len(df) if not df.empty else 0,
            }
        )
        persist_workspace_snapshot(question, st.session_state.get("active_intent") or question, sql, df)
    except Exception as exc:
        st.error("Query failed. Try rephrasing.")
        st.code(str(exc))
        append_live_log("system", f"Workflow failed: {str(exc)}")
        stream = st.session_state.streaming_workflow
        failed_at = current_timestamp()
        stream["status"] = "failed"
        stream["completed_at"] = failed_at
        stream["updated_at"] = failed_at
        st.session_state.streaming_workflow = stream
        sync_live_state_from_stream()
        if sql:
            st.code(sql, language="sql")
    finally:
        st.session_state.is_executing = False


def render_schema(schema_visible):
    if schema_visible:
        ensure_schema_semantics()
        with st.expander("Database Schema", expanded=False):
            st.code(get_schema())


def render_analytics_workspace(client):
    df = st.session_state.latest_df
    telemetry = st.session_state.workflow_telemetry
    exec_time = st.session_state.latest_exec_time
    history = st.session_state.history
    active_mode = "CSV Workspace" if st.session_state.latest_mode == "csv" and df is not None else "Live SQL"
    if df is None and not st.session_state.get("semantic_context"):
        ensure_schema_semantics()

    top_metrics = [
        {
            "label": "Active Rows",
            "value": f"{len(df):,}" if df is not None else "0",
            "caption": "Current dataset in focus",
        },
        {
            "label": "Queries Run",
            "value": len(history),
            "caption": "Session workflow executions",
        },
        {
            "label": "Execution Time",
            "value": f"{exec_time:.2f}s" if exec_time is not None else "Standby",
            "caption": "Latest end-to-end latency",
        },
        {
            "label": "Estimated Cost",
            "value": f'${telemetry.get("cost_usd", 0.0):.4f}',
            "caption": telemetry.get("model") or "Awaiting model run",
        },
    ]
    render_kpi_cards(top_metrics)

    widget_data = [
        {
            "label": "Active Mode",
            "value": active_mode,
            "caption": "Switches automatically between workflow-backed SQL and uploaded CSV analysis.",
            "badge": "Online" if df is not None else "Idle",
        },
        {
            "label": "Copilot State",
            "value": st.session_state.latest_question or "Awaiting prompt",
            "caption": "Latest question currently shaping the analytics canvas.",
            "badge": "Ready",
        },
        {
            "label": "Telemetry",
            "value": f'{telemetry.get("total_tokens", 0):,} tokens' if telemetry else "No usage yet",
            "caption": "Prompt, completion, and latency visibility for enterprise governance.",
            "badge": telemetry.get("model") or "Standby",
        },
    ]
    render_glass_widgets(widget_data)
    active_trace = st.session_state.live_trace or st.session_state.workflow_trace
    active_telemetry = st.session_state.live_telemetry or telemetry
    st.markdown(
        render_orchestration_status_badges(
            active_trace,
            active_telemetry,
            is_executing=st.session_state.get("is_executing", False),
        ),
        unsafe_allow_html=True,
    )
    workflow_left, workflow_right = st.columns([1.1, 0.9], gap="medium")
    with workflow_left:
        st.markdown(render_workflow_timeline_cards(active_trace), unsafe_allow_html=True)
    with workflow_right:
        st.markdown(
            render_active_agent_monitoring(
                active_trace,
                active_telemetry,
                is_executing=st.session_state.get("is_executing", False),
            ),
            unsafe_allow_html=True,
        )
    question = render_command_bar()
    live_panel_placeholder = st.empty()
    if st.session_state.get("pending_monitoring_run") or monitoring_due(st.session_state.get("monitoring_config", {})):
        st.session_state.pending_monitoring_run = False
        run_monitoring_workflow(live_placeholder=live_panel_placeholder)
        telemetry = st.session_state.workflow_telemetry
        exec_time = st.session_state.latest_exec_time
    elif question:
        run_query(question, live_placeholder=live_panel_placeholder)
        df = st.session_state.latest_df
        telemetry = st.session_state.workflow_telemetry
        exec_time = st.session_state.latest_exec_time
    elif st.session_state.live_logs and st.session_state.latest_question:
        with live_panel_placeholder.container():
            render_live_execution_panel(
                st.session_state.latest_question,
                st.session_state.live_trace or st.session_state.workflow_trace,
                st.session_state.live_logs,
                st.session_state.live_telemetry or st.session_state.workflow_telemetry,
                chart_key=next_plotly_key("workflow_chart_summary"),
            )

    if df is None:
        status_left, status_right = st.columns([1.45, 0.92], gap="medium")
        with status_left:
            system_metrics = [
                {"label": "System Health", "value": "99.98%", "caption": "Service readiness across AI orchestration"},
                {"label": "Active Agents", "value": "4", "caption": "Core agents on warm standby"},
                {"label": "Avg Latency", "value": "842 ms", "caption": "Trailing control-plane estimate"},
                {"label": "Signal Quality", "value": "96.4", "caption": "Composite confidence benchmark"},
            ]
            render_kpi_cards(system_metrics)
            st.markdown(
                """
                <div class="workspace-shell compact-shell">
                    <div class="section-title">Operations Canvas</div>
                    <div class="section-subtitle">Mock analytics view that keeps the workspace populated and operational between runs.</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.plotly_chart(
                build_default_operations_figure(),
                width="stretch",
                key=next_plotly_key("default_ops_chart"),
            )
            st.markdown(render_agent_row(build_default_agent_states()), unsafe_allow_html=True)
        with status_right:
            st.markdown(
                render_response_card(
                    "Analytics Ready",
                    "The workspace is preloaded with operational defaults until the next query executes.",
                    '<div class="workspace-body-copy">Launch a sample prompt or ask your own question below. Until then, the dashboard stays populated with live-looking orchestration posture, health metrics, and recommendations.</div>',
                    tone="summary-module",
                ),
                unsafe_allow_html=True,
            )
            st.markdown(render_activity_feed(build_default_activity_feed()), unsafe_allow_html=True)
            st.markdown(
                render_recommendation_card(
                    [
                        "Start with a revenue, customer, or top-track query to immediately populate the executive workspace.",
                        "Upload a CSV to inspect ad hoc datasets while keeping observability and orchestration modules available.",
                        "Use the workflow rail above to sanity-check which agent stages should remain warm for your next run.",
                    ]
                ),
                unsafe_allow_html=True,
            )
            st.markdown(
                render_observability_card(
                    {
                        "model": "gpt-4.1-mini",
                        "total_tokens": 18240,
                        "latency_ms": 842,
                        "cost_usd": 0.021384,
                    },
                    [{"step": "planner", "status": "success"}],
                ),
                unsafe_allow_html=True,
            )
            st.markdown(render_semantic_profile_card(st.session_state.get("semantic_context")), unsafe_allow_html=True)
            st.markdown(
                render_workspace_card(
                    st.session_state.get("user_identity"),
                    st.session_state.get("workspace_memory"),
                ),
                unsafe_allow_html=True,
            )
            st.markdown(render_analytics_memory_card(st.session_state.get("analytics_memory")), unsafe_allow_html=True)
            st.markdown(render_autonomous_insight_card(st.session_state.get("autonomous_insights")), unsafe_allow_html=True)
            st.markdown(render_investigation_card(st.session_state.get("investigation_state")), unsafe_allow_html=True)
            st.markdown(
                render_monitoring_card(
                    st.session_state.get("monitoring_state"),
                    st.session_state.get("monitoring_config"),
                ),
                unsafe_allow_html=True,
            )
            st.markdown(render_executive_briefing_card(st.session_state.get("executive_briefing")), unsafe_allow_html=True)
        return
    main_left, main_right = st.columns([1.42, 0.92], gap="medium")
    with main_left:
        st.markdown(
            render_executive_summary(st.session_state.latest_question, df, exec_time, telemetry),
            unsafe_allow_html=True,
        )
        st.markdown(render_semantic_profile_card(st.session_state.get("semantic_context")), unsafe_allow_html=True)
        st.markdown(
            render_workspace_card(
                st.session_state.get("user_identity"),
                st.session_state.get("workspace_memory"),
            ),
            unsafe_allow_html=True,
        )
        st.markdown(render_analytics_memory_card(st.session_state.get("analytics_memory")), unsafe_allow_html=True)

        chart_rendered = False
        if is_scalar_result(df):
            scalar_col = df.columns[0]
            scalar_value = df.iloc[0, 0]
            render_kpi_cards(
                [
                    {
                        "label": scalar_col,
                        "value": scalar_value,
                        "caption": "Single-value result surfaced as a KPI",
                    }
                ]
            )
        elif can_render_chart(df):
            st.markdown(
                """
                <div class="workspace-shell compact-shell">
                    <div class="section-title">Visualization Workspace</div>
                    <div class="section-subtitle">Interactive insight canvas for executive-ready narratives and deeper operator exploration.</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            all_options = build_column_options(df)
            numeric_options = get_numeric_column_options(df)
            numeric_labels = [option["label"] for option in numeric_options]
            all_labels = [option["label"] for option in all_options]
            option_lookup = {option["label"]: option for option in all_options}
            recommended_x, recommended_y = recommend_chart_fields(df, st.session_state.get("semantic_context"))
            if st.session_state.x_col not in all_labels and recommended_x in all_labels:
                st.session_state.x_col = recommended_x
            if st.session_state.y_col not in numeric_labels and recommended_y in numeric_labels:
                st.session_state.y_col = recommended_y

            c1, c2, c3 = st.columns(3, gap="small")
            with c1:
                x_col = st.selectbox(
                    "X-axis",
                    all_labels,
                    index=all_labels.index(st.session_state.x_col)
                    if st.session_state.x_col in all_labels
                    else 0,
                )
                st.session_state.x_col = x_col

            with c2:
                y_options = [label for label in numeric_labels if label != x_col]
                if y_options:
                    y_col = st.selectbox(
                        "Y-axis",
                        y_options,
                        index=y_options.index(st.session_state.y_col)
                        if st.session_state.y_col in y_options
                        else 0,
                    )
                    st.session_state.y_col = y_col
                else:
                    y_col = None

            with c3:
                chart_type = st.selectbox(
                    "Chart Type",
                    ["Bar", "Line", "Area"],
                    index=["Bar", "Line", "Area"].index(st.session_state.chart_type),
                )
                st.session_state.chart_type = chart_type
                if st.session_state.get("analytics_memory"):
                    memory = dict(st.session_state.analytics_memory)
                    memory["previous_chart"] = current_chart_state()
                    st.session_state.analytics_memory = memory

            x_option = option_lookup[x_col]
            y_option = option_lookup[y_col] if y_col else None
            x_series = df.iloc[:, x_option["index"]]

            if pd.api.types.is_object_dtype(x_series) or pd.api.types.is_string_dtype(x_series):
                selected_values = st.multiselect(
                    f"Filter {x_col}",
                    x_series.dropna().unique(),
                    default=x_series.dropna().unique(),
                )
                filtered_df = df[x_series.isin(selected_values)]
            else:
                filtered_df = df

            if y_option is not None:
                chart_df = pd.DataFrame(
                    {
                        x_col: filtered_df.iloc[:, x_option["index"]],
                        y_col: filtered_df.iloc[:, y_option["index"]],
                    }
                ).dropna()
                if not chart_df.empty:
                    fig = build_plotly_figure(chart_df, x_col, y_col, chart_type)
                    st.plotly_chart(
                        fig,
                        width="stretch",
                        key=next_plotly_key("insight_chart"),
                    )
                    chart_rendered = True
            if not chart_rendered:
                render_result_table_card(df, height=230)
        else:
            render_result_table_card(df, height=250)

    with main_right:
        recommendations = build_ai_recommendations(df, telemetry, st.session_state.workflow_trace)
        st.markdown(render_recommendation_card(recommendations), unsafe_allow_html=True)
        st.markdown(render_autonomous_insight_card(st.session_state.get("autonomous_insights")), unsafe_allow_html=True)
        st.markdown(render_investigation_card(st.session_state.get("investigation_state")), unsafe_allow_html=True)
        st.markdown(
            render_monitoring_card(
                st.session_state.get("monitoring_state"),
                st.session_state.get("monitoring_config"),
            ),
            unsafe_allow_html=True,
        )
        st.markdown(render_executive_briefing_card(st.session_state.get("executive_briefing")), unsafe_allow_html=True)
        st.markdown(render_observability_card(telemetry, st.session_state.workflow_trace), unsafe_allow_html=True)

        if not df.empty:
            explanation = st.session_state.get("latest_insight", "")
            if explanation:
                st.markdown(
                    render_response_card(
                        "AI Insight Brief",
                        "Natural-language interpretation of the current result set.",
                        f'<div class="workspace-body-copy">{escape_html(explanation)}</div>',
                        tone="insight-module",
                    ),
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    render_response_card(
                        "AI Insight Brief",
                        "Natural-language interpretation of the current result set.",
                        '<div class="workspace-body-copy">Insight narration is unavailable for this run.</div>',
                        tone="insight-module",
                    ),
                    unsafe_allow_html=True,
                )

    show_sql = bool(st.session_state.latest_sql)
    show_secondary_preview = not df.empty and (is_scalar_result(df) or can_render_chart(df))
    if show_sql and show_secondary_preview:
        lower_left, lower_right = st.columns([1.1, 1.18], gap="medium")
        with lower_left:
            render_sql_card(st.session_state.latest_sql)
        with lower_right:
            render_result_table_card(df, height=210)
    elif show_sql:
        render_sql_card(st.session_state.latest_sql)
    elif show_secondary_preview:
        render_result_table_card(df, height=210)

    if not df.empty:
        st.download_button(
            "Download CSV",
            df.to_csv(index=False).encode(),
            "result.csv",
            "text/csv",
            width="stretch",
        )


def render_copilot_workspace():
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
        render_workflow_timeline(
            st.session_state.workflow_trace,
            chart_key=next_plotly_key("workflow_chart_copilot"),
        )
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


def render_telemetry_exports(telemetry, trace, scope="workspace"):
    telemetry = validate_telemetry_payload(telemetry)
    rows = telemetry_export_rows(telemetry, trace)
    payload = {
        "telemetry": telemetry,
        "trace": trace,
        "events": st.session_state.get("streaming_workflow", {}).get("telemetry_events", []),
        "latency_breakdown": phase_latency_breakdown(telemetry),
        "exported_at": current_timestamp(),
    }
    left, right = st.columns(2)
    with left:
        st.download_button(
            "Export Telemetry JSON",
            json.dumps(payload, indent=2).encode("utf-8"),
            f"{scope}-telemetry.json",
            "application/json",
            width="stretch",
        )
    with right:
        csv_df = pd.DataFrame(rows or [{"correlation_id": telemetry.get("correlation_id"), "step": "none"}])
        st.download_button(
            "Export Telemetry CSV",
            csv_df.to_csv(index=False).encode("utf-8"),
            f"{scope}-telemetry.csv",
            "text/csv",
            width="stretch",
        )


def render_platform_summary():
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


def current_operations_summary():
    return operations_summary(
        memory=st.session_state.get("workspace_memory", {}),
        telemetry=st.session_state.live_telemetry or st.session_state.workflow_telemetry,
        trace=st.session_state.live_trace or st.session_state.workflow_trace,
        execution_graph=st.session_state.get("latest_execution_graph", {}),
        is_executing=st.session_state.get("is_executing", False),
    )


def render_health_banner(summary):
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


def render_operations_center():
    telemetry = validate_telemetry_payload(st.session_state.live_telemetry or st.session_state.workflow_telemetry)
    trace = st.session_state.live_trace or st.session_state.workflow_trace
    memory = st.session_state.get("workspace_memory", {})
    graph = st.session_state.get("latest_execution_graph", {})
    summary = current_operations_summary()
    render_health_banner(summary)
    render_kpi_cards(
        [
            {
                "label": "Active Workflows",
                "value": summary["active_workflows"],
                "caption": "Local workspace workflows currently executing.",
            },
            {
                "label": "Agent Utilization",
                "value": summary["active_agents"],
                "caption": "Agents in running or retrying states.",
            },
            {
                "label": "Token Volume",
                "value": f'{summary["total_tokens"]:,}',
                "caption": "Persisted and active workflow token usage.",
            },
            {
                "label": "Runtime Cost",
                "value": f'${summary["estimated_cost_usd"]:.4f}',
                "caption": "Estimated model spend across workspace telemetry.",
            },
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
        render_telemetry_exports(telemetry, trace, scope="operations")


def render_execution_graph_card(graph, confidence, recovery, policy_decision=None):
    nodes = graph.get("nodes", []) if graph else []
    body = "".join(
        (
            f'<div class="workspace-list-item">'
            f'<div class="observability-label">{escape_html(node.get("name", ""))} · {escape_html(node.get("status", "queued")).upper()}</div>'
            f'<div class="workspace-body-copy">Phase: {escape_html(node.get("phase", ""))}<br/>'
            f'Dependencies: {escape_html(", ".join(node.get("dependencies", [])) or "none")}<br/>'
            f'Confidence: {escape_html(node.get("confidence", 0.0))}</div>'
            f"</div>"
        )
        for node in nodes
    )
    if recovery:
        body += (
            f'<div class="workspace-list-item">'
            f'<div class="observability-label">Recovery · {escape_html(recovery.get("strategy", "none"))}</div>'
            f'<div class="workspace-body-copy">{escape_html(recovery.get("message", ""))}</div>'
            f"</div>"
        )
    if confidence:
        body += (
            '<div class="workspace-list-item">'
            '<div class="observability-label">Stage Confidence</div>'
            '<div class="workspace-body-copy">'
            + "<br/>".join(f"{escape_html(k)}: {escape_html(v)}" for k, v in confidence.items())
            + "</div></div>"
        )
    if policy_decision:
        body += (
            '<div class="workspace-list-item">'
            f'<div class="observability-label">Policy Decision · {escape_html(policy_decision.get("action", "continue")).upper()}</div>'
            f'<div class="workspace-body-copy">{escape_html(policy_decision.get("reason", ""))}<br/>'
            f'Stage: {escape_html(policy_decision.get("stage", ""))}<br/>'
            f'Retry Budget: {escape_html(policy_decision.get("retry_count", 0))}/{escape_html(policy_decision.get("max_retries", 0))}</div>'
            "</div>"
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
    body = (
        '<div class="observability-grid">'
        + "".join(
            f'<div class="observability-metric"><div class="observability-label">{escape_html(key)}</div>'
            f'<div class="observability-value">{escape_html(value)}</div></div>'
            for key, value in categories.items()
        )
        + "</div>"
    )
    body += "".join(
        f'<div class="workspace-list-item"><div class="observability-label">Retrieval candidate · {escape_html(item.get("run_id", ""))}</div>'
        f'<div class="workspace-body-copy">{escape_html(item.get("question", ""))}<br/>Rows: {escape_html(item.get("rows", 0))}<br/>'
        f'Confidence: {escape_html(item.get("retrieval_confidence", 0.0))}</div></div>'
        for item in recent_queries
    )
    return render_response_card(
        "Semantic Memory Inspection",
        "Categorized workspace memory with deduplicated recent retrieval candidates.",
        body,
        tone="default-module",
    )


def render_session_replay_card(memory):
    sessions = list(reversed((memory or {}).get("sessions", [])[-5:]))
    body = "".join(
        (
            f'<div class="workspace-list-item">'
            f'<div class="observability-label">{escape_html(session.get("session_id", ""))} · {escape_html(session.get("status", ""))}</div>'
            f'<div class="workspace-body-copy">Started: {escape_html(session.get("started_at", ""))}<br/>'
            f'Workflows: {escape_html(len(session.get("workflow_ids", [])))}<br/>'
            f'Transcripts: {escape_html(len(session.get("transcripts", [])))}</div>'
            f"</div>"
        )
        for session in sessions
    )
    return render_response_card(
        "Session Replay",
        "Persisted workspace sessions and exportable workflow transcript counts.",
        body or '<div class="workspace-body-copy">No persisted sessions yet.</div>',
        tone="summary-module",
    )


def render_investigations_workspace():
    render_platform_summary()
    identity = st.session_state.get("user_identity")
    memory = st.session_state.get("workspace_memory", {})
    current = st.session_state.get("investigation_state")
    stored = memory.get("investigations", [])
    left, right = st.columns([1.15, 0.85], gap="medium")
    with left:
        st.markdown(render_investigation_card(current), unsafe_allow_html=True)
        if st.button("Bookmark Current Investigation", width="stretch"):
            persist_investigation_bookmark()
            st.success("Investigation bookmarked for this workspace session.")
        st.markdown(render_workflow_timeline_cards(st.session_state.live_trace or st.session_state.workflow_trace), unsafe_allow_html=True)
    with right:
        st.markdown(
            render_response_card(
                "Investigation Sessions",
                "Persisted autonomous drill-down sessions for this workspace.",
                "".join(
                    f'<div class="workspace-list-item"><div class="observability-label">{escape_html(item.get("run_id", "run"))}</div>'
                    f'<div class="workspace-body-copy">{escape_html(item.get("summary", ""))}</div></div>'
                    for item in reversed(stored[-6:])
                )
                or '<div class="workspace-body-copy">No persisted investigation sessions yet.</div>',
                tone="insight-module",
            ),
            unsafe_allow_html=True,
        )
        st.markdown(render_workspace_card(identity, memory), unsafe_allow_html=True)
        st.markdown(render_semantic_profile_card(st.session_state.get("semantic_context")), unsafe_allow_html=True)
        st.markdown(render_session_replay_card(memory), unsafe_allow_html=True)
        recommendation_df = st.session_state.latest_df if st.session_state.latest_df is not None else pd.DataFrame()
        st.markdown(
            render_recommendation_card(
                build_ai_recommendations(
                    recommendation_df,
                    st.session_state.workflow_telemetry,
                    st.session_state.workflow_trace,
                )
            ),
            unsafe_allow_html=True,
        )


def render_monitoring_workspace():
    render_platform_summary()
    memory = st.session_state.get("workspace_memory", {})
    telemetry_runs = memory.get("telemetry_summaries", [])
    failed_runs = [item for item in telemetry_runs if item.get("error_type")]
    avg_latency = (
        sum(item.get("latency_ms", 0) for item in telemetry_runs) / len(telemetry_runs)
        if telemetry_runs
        else 0
    )
    render_kpi_cards(
        [
            {
                "label": "Workflow Throughput",
                "value": len(memory.get("workflow_runs", [])),
                "caption": "Persisted workflow runs in this workspace.",
            },
            {
                "label": "Rolling Latency",
                "value": f"{avg_latency:.0f} ms" if telemetry_runs else "Standby",
                "caption": "Average latency across persisted telemetry summaries.",
            },
            {
                "label": "Error Rate",
                "value": f"{(len(failed_runs) / len(telemetry_runs) * 100):.1f}%" if telemetry_runs else "0.0%",
                "caption": "Share of runs with captured error telemetry.",
            },
            {
                "label": "Runtime Uptime",
                "value": "Online",
                "caption": "Streamlit session and backend diagnostics are responding.",
            },
        ]
    )
    left, right = st.columns([1, 1], gap="medium")
    with left:
        st.markdown(
            render_monitoring_card(
                st.session_state.get("monitoring_state"),
                st.session_state.get("monitoring_config"),
            ),
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
                    for item in reversed(st.session_state.get("monitoring_runs", [])[-8:])
                )
                or '<div class="workspace-body-copy">No monitoring run history yet.</div>',
                tone="observability-module",
            ),
            unsafe_allow_html=True,
        )
        render_telemetry_exports(st.session_state.workflow_telemetry, st.session_state.workflow_trace, scope="monitoring")


def render_agents_workspace():
    telemetry = validate_telemetry_payload(st.session_state.live_telemetry or st.session_state.workflow_telemetry)
    trace = st.session_state.live_trace or st.session_state.workflow_trace
    render_platform_summary()
    left, right = st.columns([0.92, 1.08], gap="medium")
    with left:
        st.markdown(
            render_active_agent_monitoring(
                trace,
                telemetry,
                is_executing=st.session_state.get("is_executing", False),
            ),
            unsafe_allow_html=True,
        )
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
        render_telemetry_exports(telemetry, trace, scope="agents")

        utilization = agent_utilization(st.session_state.get("latest_execution_graph", {}))
        if utilization:
            st.dataframe(pd.DataFrame(utilization), width="stretch", height=220)


def render_api_workspace():
    telemetry = validate_telemetry_payload(st.session_state.live_telemetry or st.session_state.workflow_telemetry)
    trace = st.session_state.live_trace or st.session_state.workflow_trace
    runtime = st.session_state.get("openai_runtime", {})
    memory = st.session_state.get("workspace_memory", {})
    workspace_report = workspace_summary(memory)
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
            "GET /health\nGET /ready\nGET /diagnostics\nPOST /execute\nGET /workflow/{workflow_id}\nGET /workflow/{workflow_id}/events\nGET /workflow/{workflow_id}/stream\nGET /workspace/{workspace_id}/inspection\nGET /workspace/{workspace_id}/transcripts\nGET /workspace/{workspace_id}/sql-history",
            language="http",
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
        render_telemetry_exports(telemetry, trace, scope="api")


st.set_page_config(
    page_title="Agentic AI Analytics Platform",
    layout="wide",
    page_icon=":bar_chart:",
)

st.markdown(get_theme_css(), unsafe_allow_html=True)
client = None
init_session_state()
st.session_state.openai_runtime = validate_openai_runtime()

render_hero()
selected_nav = render_top_navigation(st.session_state.get("top_navigation", "Overview"))
st.session_state.workspace_route = selected_nav
sidebar_state = render_sidebar()
configure_workspace_session(
    sidebar_state["workspace_user"],
    sidebar_state["workspace_team"],
    sidebar_state["workspace_role"],
)
st.session_state.monitoring_config = {
    **st.session_state.get("monitoring_config", default_monitoring_config()),
    "enabled": sidebar_state["monitoring_enabled"],
    "targets": sidebar_state["monitoring_targets"],
    "interval_minutes": sidebar_state["monitoring_interval"],
}
if sidebar_state["run_monitoring"]:
    st.session_state.pending_monitoring_run = True

if sidebar_state["clear_chat"]:
    clear_session()
    st.rerun()

if sidebar_state["uploaded_file"] is not None:
    uploaded_name = sidebar_state["uploaded_file"].name
    st.session_state.uploaded_df = pd.read_csv(sidebar_state["uploaded_file"])
    if st.session_state.uploaded_name != uploaded_name:
        st.session_state.uploaded_name = uploaded_name
        profile_active_dataframe(st.session_state.uploaded_df, f"Uploaded CSV: {uploaded_name}")
        st.success("CSV uploaded successfully. The workspace is now using uploaded data.")

render_schema(sidebar_state["show_schema"])

nav = st.session_state.get("workspace_route") or sidebar_state["nav"]
if nav == "Overview":
    render_analytics_workspace(client)
elif nav == "Operations":
    render_operations_center()
elif nav == "Copilot":
    render_copilot_workspace()
elif nav == "Investigations":
    render_investigations_workspace()
elif nav == "Monitoring":
    render_monitoring_workspace()
elif nav == "Agents":
    render_agents_workspace()
elif nav == "API":
    render_api_workspace()
else:
    render_history(st.session_state.history)

render_footer()
