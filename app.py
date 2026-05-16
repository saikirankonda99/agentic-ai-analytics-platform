import os
import time

import pandas as pd
import streamlit as st
from openai import OpenAI

from db import get_schema
from styles.theme import get_theme_css
from ui.dashboard import (
    build_plotly_figure,
    build_default_operations_figure,
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
    render_recommendation_card,
    render_result_table_card,
    render_response_card,
    render_sidebar,
    render_live_execution_panel,
    render_observability_card,
    render_sql_card,
    render_telemetry_panel,
    render_workflow_timeline,
)

try:
    from graph.workflow import run_workflow
except Exception:
    run_workflow = None


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
    res = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[{"role": "user", "content": prompt}],
    )
    return res.choices[0].message.content


def build_ai_recommendations(df, telemetry, trace):
    recommendations = []
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
        "latest_mode": "database",
        "uploaded_name": None,
        "command_text": "",
        "run_id": "default",
        "run_counter": 0,
        "live_render_seq": 0,
        "live_trace": [],
        "live_logs": [],
        "live_telemetry": {},
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
    st.session_state.latest_mode = "database"
    st.session_state.uploaded_name = None
    st.session_state.command_text = ""
    st.session_state.run_id = "default"
    st.session_state.run_counter = 0
    st.session_state.live_render_seq = 0
    st.session_state.live_trace = []
    st.session_state.live_logs = []
    st.session_state.live_telemetry = {}
    st.session_state.is_executing = False
    st.session_state.x_col = None
    st.session_state.y_col = None
    st.session_state.chart_type = "Bar"
    if "uploaded_df" in st.session_state:
        del st.session_state["uploaded_df"]


def enrich_trace_with_telemetry(trace, telemetry):
    telemetry_steps = {item.get("step"): item for item in telemetry.get("steps", [])} if telemetry else {}
    enriched = []
    for item in trace:
        combined = dict(item)
        step_meta = telemetry_steps.get(item.get("step"), {})
        for key in ("model", "latency_ms", "prompt_tokens", "completion_tokens", "total_tokens", "cost_usd"):
            if key in step_meta:
                combined[key] = step_meta.get(key)
        enriched.append(combined)
    return enriched


def append_live_log(step, message):
    st.session_state.live_logs.append(
        {
            "time": time.strftime("%H:%M:%S"),
            "step": step,
            "message": message,
        }
    )


def render_live_workspace_snapshot(question, placeholder):
    with placeholder.container():
        render_live_execution_panel(
            question,
            st.session_state.live_trace,
            st.session_state.live_logs,
            st.session_state.live_telemetry,
            chart_key=f"workflow_chart_{st.session_state.run_id}_{st.session_state.live_render_seq}",
        )


def run_query(question, live_placeholder=None):
    st.session_state.messages.append({"role": "user", "content": question})
    start = time.time()
    sql = ""
    workflow_result = None
    st.session_state.run_counter += 1
    st.session_state.run_id = f"run_{st.session_state.run_counter}"
    st.session_state.live_render_seq = 0
    st.session_state.is_executing = True
    st.session_state.live_trace = []
    st.session_state.live_logs = []
    st.session_state.live_telemetry = {}

    def workflow_callback(phase, state_snapshot, step, detail):
        telemetry = state_snapshot.get("telemetry", {})
        trace = state_snapshot.get("trace", [])
        if phase == "active":
            live_trace = enrich_trace_with_telemetry(trace, telemetry)
            live_trace.append({"step": step, "status": "active", "detail": detail})
            st.session_state.live_trace = live_trace
        else:
            st.session_state.live_trace = enrich_trace_with_telemetry(trace, telemetry)
        st.session_state.live_telemetry = telemetry
        append_live_log(step, detail)
        if live_placeholder is not None:
            st.session_state.live_render_seq += 1
            render_live_workspace_snapshot(question, live_placeholder)

    try:
        if "uploaded_df" in st.session_state:
            df = st.session_state.uploaded_df
            st.session_state.workflow_trace = []
            st.session_state.workflow_telemetry = {}
            mode = "csv"
            append_live_log("ingestion", "Uploaded CSV loaded into the analytics workspace.")
            if live_placeholder is not None:
                render_live_workspace_snapshot(question, live_placeholder)
        else:
            if run_workflow is None:
                st.error("Workflow is unavailable.")
                return

            if live_placeholder is not None:
                render_live_workspace_snapshot(question, live_placeholder)

            workflow_result = run_workflow(question, callback=workflow_callback)
            st.session_state.workflow_trace = workflow_result.get("trace", [])
            st.session_state.workflow_telemetry = workflow_result.get("telemetry", {})
            sql = (workflow_result.get("sql") or "").strip()
            workflow_error = workflow_result.get("error")

            if workflow_error:
                st.error(workflow_error)
                if sql:
                    st.code(sql, language="sql")
                return

            cols = workflow_result.get("columns", [])
            rows = workflow_result.get("rows", [])
            if not cols:
                st.warning("No columns returned or query failed.")
                return
            df = pd.DataFrame(rows, columns=cols)
            mode = "database"

        exec_time = time.time() - start
        st.session_state.latest_df = df
        st.session_state.latest_sql = sql
        st.session_state.latest_question = question
        st.session_state.latest_exec_time = exec_time
        st.session_state.latest_mode = mode
        st.session_state.live_trace = enrich_trace_with_telemetry(
            st.session_state.workflow_trace,
            st.session_state.workflow_telemetry,
        )
        st.session_state.live_telemetry = st.session_state.workflow_telemetry
        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": f"Query executed successfully. Returned {len(df)} rows.",
            }
        )
        append_live_log("system", f"Workflow completed successfully in {exec_time:.2f}s.")
        st.session_state.history.append(
            {
                "question": question,
                "sql": sql,
                "rows": len(df) if not df.empty else 0,
            }
        )
    except Exception as exc:
        st.error("Query failed. Try rephrasing.")
        st.code(str(exc))
        append_live_log("system", f"Workflow failed: {str(exc)}")
        if sql:
            st.code(sql, language="sql")
    finally:
        st.session_state.is_executing = False


def render_schema(schema_visible):
    if schema_visible:
        with st.expander("Database Schema", expanded=False):
            st.code(get_schema())


def render_analytics_workspace(client):
    df = st.session_state.latest_df
    telemetry = st.session_state.workflow_telemetry
    exec_time = st.session_state.latest_exec_time
    history = st.session_state.history
    active_mode = "CSV Workspace" if st.session_state.latest_mode == "csv" and df is not None else "Live SQL"

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
    question = render_command_bar()
    live_panel_placeholder = st.empty()
    if question:
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
                chart_key=f"workflow_chart_{st.session_state.run_id}_summary",
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
                use_container_width=True,
                key=f"default_ops_chart_{st.session_state.run_id}",
            )
            render_agent_row(build_default_agent_states())
        with status_right:
            render_response_card(
                "Analytics Ready",
                "The workspace is preloaded with operational defaults until the next query executes.",
                """
                <div class="workspace-body-copy">
                    Launch a sample prompt or ask your own question below. Until then, the dashboard stays populated
                    with live-looking orchestration posture, health metrics, and recommendations.
                </div>
                """,
                tone="summary-module",
            )
            render_activity_feed(build_default_activity_feed())
            render_recommendation_card(
                [
                    "Start with a revenue, customer, or top-track query to immediately populate the executive workspace.",
                    "Upload a CSV to inspect ad hoc datasets while keeping observability and orchestration modules available.",
                    "Use the workflow rail above to sanity-check which agent stages should remain warm for your next run.",
                ]
            )
            render_observability_card(
                {
                    "model": "gpt-4.1-mini",
                    "total_tokens": 18240,
                    "latency_ms": 842,
                    "cost_usd": 0.021384,
                },
                [{"step": "planner", "status": "success"}],
            )
        return
    main_left, main_right = st.columns([1.42, 0.92], gap="medium")
    with main_left:
        render_executive_summary(st.session_state.latest_question, df, exec_time, telemetry)

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
                        use_container_width=True,
                        key=f"insight_chart_{st.session_state.run_id}",
                    )
                    chart_rendered = True
            if not chart_rendered:
                render_result_table_card(df, height=230)
        else:
            render_result_table_card(df, height=250)

    with main_right:
        recommendations = build_ai_recommendations(df, telemetry, st.session_state.workflow_trace)
        render_recommendation_card(recommendations)
        render_observability_card(telemetry, st.session_state.workflow_trace)

        if not df.empty:
            try:
                explanation = explain_result(client, st.session_state.latest_question, df)
                render_response_card(
                    "AI Insight Brief",
                    "Natural-language interpretation of the current result set.",
                    f'<div class="workspace-body-copy">{explanation}</div>',
                    tone="insight-module",
                )
            except Exception as exc:
                render_response_card(
                    "AI Insight Brief",
                    "Natural-language interpretation of the current result set.",
                    f'<div class="workspace-body-copy">AI explanation is temporarily unavailable.<br/>{str(exc)}</div>',
                    tone="insight-module",
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
            use_container_width=True,
        )


def render_copilot_workspace():
    left, right = st.columns([0.92, 1.08])
    with left:
        render_chat_history(st.session_state.messages)
    with right:
        render_workflow_timeline(
            st.session_state.workflow_trace,
            chart_key=f"workflow_chart_copilot_{st.session_state.run_id}",
        )
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
            st.dataframe(st.session_state.latest_df.head(20), use_container_width=True, height=280)


st.set_page_config(
    page_title="GenAI SQL Assistant",
    layout="wide",
    page_icon=":bar_chart:",
)

st.markdown(get_theme_css(), unsafe_allow_html=True)
client = OpenAI(api_key=get_openai_api_key())
init_session_state()

render_hero()
sidebar_state = render_sidebar()

if sidebar_state["clear_chat"]:
    clear_session()
    st.rerun()

if sidebar_state["uploaded_file"] is not None:
    uploaded_name = sidebar_state["uploaded_file"].name
    st.session_state.uploaded_df = pd.read_csv(sidebar_state["uploaded_file"])
    if st.session_state.uploaded_name != uploaded_name:
        st.session_state.uploaded_name = uploaded_name
        st.success("CSV uploaded successfully. The workspace is now using uploaded data.")

render_schema(sidebar_state["show_schema"])

nav = sidebar_state["nav"]
if nav == "Overview":
    render_analytics_workspace(client)
elif nav == "Copilot":
    render_copilot_workspace()
else:
    render_history(st.session_state.history)

render_footer()
