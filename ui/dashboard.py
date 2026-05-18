from __future__ import annotations

from html import escape

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


STATUS_META = {
    "idle": {"label": "Idle", "color": "#64748b"},
    "active": {"label": "Active", "color": "#56ccf2"},
    "success": {"label": "Success", "color": "#34d399"},
    "warning": {"label": "Warning", "color": "#fbbf24"},
    "error": {"label": "Error", "color": "#f87171"},
    "retry": {"label": "Warning", "color": "#fbbf24"},
    "pending": {"label": "Idle", "color": "#64748b"},
}

WORKFLOW_STEPS = [
    "planner",
    "schema retrieval",
    "memory retrieval",
    "sql generation",
    "validation",
    "reflection",
    "execution",
]

STEP_META = {
    "planner": {"title": "Planner", "caption": "Intent routing"},
    "schema retrieval": {"title": "Schema", "caption": "Context retrieval"},
    "memory retrieval": {"title": "Memory", "caption": "History recall"},
    "sql generation": {"title": "SQL Agent", "caption": "Query synthesis"},
    "validation": {"title": "Validation", "caption": "Guardrail checks"},
    "reflection": {"title": "Reflection", "caption": "Self-correction"},
    "execution": {"title": "Execution", "caption": "Warehouse run"},
}

SAMPLE_PROMPTS = [
    "List all customers",
    "Top 10 customers by invoices",
    "Revenue by country",
    "Tracks with album and artist",
]


# ---------------------------------------------------------------------------
# HTML primitives
# ---------------------------------------------------------------------------


def escape_html(value: object) -> str:
    return escape("" if value is None else str(value), quote=True)


def markdown_html(html: str) -> None:
    st.markdown(html, unsafe_allow_html=True)


def section_header_html(title: str, subtitle: str, class_name: str = "section-card compact-card") -> str:
    return (
        f'<div class="{class_name}">'
        f'<div class="section-title">{escape_html(title)}</div>'
        f'<div class="section-subtitle">{escape_html(subtitle)}</div>'
        f"</div>"
    )


def response_body_html(body_html: str) -> str:
    return f'<div class="workspace-module-body">{body_html}</div>'


def render_response_card(
    title: str,
    subtitle: str,
    body_html: str,
    tone: str = "default",
) -> str:
    return (
        f'<div class="workspace-module {tone}">'
        f'<div class="workspace-module-head">'
        f'<div class="section-title">{escape_html(title)}</div>'
        f'<div class="section-subtitle">{escape_html(subtitle)}</div>'
        f"</div>"
        f"{response_body_html(body_html)}"
        f"</div>"
    )


def metric_grid_html(items: list[tuple[str, object]]) -> str:
    return "".join(
        (
            f'<div class="observability-metric">'
            f'<div class="observability-label">{escape_html(label)}</div>'
            f'<div class="observability-value">{escape_html(value)}</div>'
            f"</div>"
        )
        for label, value in items
    )


# ---------------------------------------------------------------------------
# Shell and navigation sections
# ---------------------------------------------------------------------------


def render_hero() -> None:
    markdown_html(
        """
        <div class="hero-card">
            <div class="hero-eyebrow">AI Analytics Workspace</div>
            <h1 class="hero-title">Enterprise analytics, orchestrated by AI</h1>
            <p class="hero-copy">
                Ask in natural language, inspect SQL, monitor workflow telemetry, and publish executive-ready
                insights from a single immersive command center.
            </p>
            <div class="hero-badges">
                <span class="hero-badge">Workflow-native</span>
                <span class="hero-badge">Executive KPIs</span>
                <span class="hero-badge">Realtime telemetry</span>
                <span class="hero-badge">Plotly canvas</span>
            </div>
        </div>
        """
    )


def render_sidebar() -> dict:
    with st.sidebar:
        markdown_html(
            """
            <div class="sidebar-brand">
                <p class="sidebar-brand-title">GenAI SQL Assistant</p>
                <div class="sidebar-brand-copy">Analytics operations cockpit for AI-native querying.</div>
            </div>
            """
        )

        nav = st.radio(
            "Workspace",
            ["Overview", "Copilot", "History"],
            label_visibility="collapsed",
        )

        st.markdown("### Control Center")
        clear_chat = st.button("Clear session", width="stretch")
        show_schema = st.toggle("Show database schema", value=False)

        st.markdown("### Sample Prompts")
        for query in SAMPLE_PROMPTS:
            markdown_html(f'<div class="sample-query">{escape_html(query)}</div>')

        st.markdown("### CSV Upload")
        uploaded_file = st.file_uploader("Upload CSV", type=["csv"], label_visibility="collapsed")

        return {
            "nav": nav,
            "clear_chat": clear_chat,
            "show_schema": show_schema,
            "uploaded_file": uploaded_file,
        }


def render_footer() -> None:
    markdown_html(
        """
        <div class="footer-note">
            Built with Streamlit and OpenAI for AI-native analytics workflows.
        </div>
        """
    )


# ---------------------------------------------------------------------------
# Command and conversation sections
# ---------------------------------------------------------------------------


def render_prompt_launcher() -> str | None:
    markdown_html(
        section_header_html(
            "Prompt Launcher",
            "Launch a workflow from a recommended question or type your own below.",
        )
    )
    c1, c2, c3 = st.columns(3)
    prompt = None
    if c1.button("Top Customers", width="stretch"):
        prompt = "Top 10 customers by invoices"
    if c2.button("Revenue by Country", width="stretch"):
        prompt = "Revenue by country"
    if c3.button("Top Tracks", width="stretch"):
        prompt = "Top 10 tracks"
    return prompt


def render_command_bar() -> str | None:
    markdown_html(
        section_header_html(
            "Command Workspace",
            "Submit a question and keep orchestration anchored to the analytics workspace.",
            class_name="workspace-shell compact-shell",
        )
    )
    prompt = None
    with st.form("command_bar_form", clear_on_submit=False):
        query_col, action_col = st.columns([6, 1.2], vertical_alignment="bottom")
        with query_col:
            question = st.text_input(
                "Command",
                value=st.session_state.get("command_text", ""),
                placeholder="Ask a revenue, customer, or product question...",
                label_visibility="collapsed",
            )
        with action_col:
            submitted = st.form_submit_button("Run", width="stretch")

    c1, c2, c3 = st.columns(3)
    if c1.button("Top Customers", width="stretch"):
        prompt = "Top 10 customers by invoices"
    if c2.button("Revenue by Country", width="stretch"):
        prompt = "Revenue by country"
    if c3.button("Top Tracks", width="stretch"):
        prompt = "Top 10 tracks"

    if submitted and question.strip():
        st.session_state.command_text = question.strip()
        return question.strip()
    if prompt:
        st.session_state.command_text = prompt
        return prompt
    return None


def chat_message_html(message: dict) -> str:
    role_class = "assistant-card" if message["role"] == "assistant" else "user-card"
    role_label = "AI Copilot" if message["role"] == "assistant" else "User Query"
    content = escape_html(message["content"]).replace("\n", "<br/>")
    return (
        f'<div class="response-card {role_class}">'
        f'<div class="response-meta">{role_label}</div>'
        f'<div class="response-content">{content}</div>'
        f"</div>"
    )


def render_chat_history(messages: list[dict]) -> None:
    markdown_html(
        section_header_html(
            "AI Copilot Conversation",
            "Every workflow run is mirrored here so the reasoning trail stays visible.",
            class_name="chat-card",
        )
    )
    if not messages:
        markdown_html(
            """
            <div class="response-card assistant-card">
                <div class="response-meta">AI Copilot</div>
                <div class="response-content">
                    Ask a question to populate the workspace with SQL, telemetry, workflow state, and executive
                    analytics.
                </div>
            </div>
            """
        )
        return

    for message in messages:
        markdown_html(chat_message_html(message))


# ---------------------------------------------------------------------------
# KPI and glass widgets
# ---------------------------------------------------------------------------


def kpi_card_html(metric: dict) -> str:
    return (
        f'<div class="kpi-card">'
        f'<div class="kpi-label">{escape_html(metric["label"])}</div>'
        f'<div class="kpi-value">{escape_html(metric["value"])}</div>'
        f'<div class="kpi-delta">{escape_html(metric["caption"])}</div>'
        f"</div>"
    )


def render_kpi_cards(metrics: list[dict]) -> None:
    columns = st.columns(len(metrics))
    for column, metric in zip(columns, metrics):
        with column:
            markdown_html(kpi_card_html(metric))


def glass_widget_html(widget: dict) -> str:
    badge = widget.get("badge")
    badge_html = f'<span class="status-pill">{escape_html(badge)}</span>' if badge else ""
    return (
        f'<div class="glass-widget">'
        f'<div class="glass-widget-top">'
        f'<div class="glass-widget-label">{escape_html(widget["label"])}</div>'
        f"{badge_html}"
        f"</div>"
        f'<div class="glass-widget-value">{escape_html(widget["value"])}</div>'
        f'<div class="glass-widget-copy">{escape_html(widget["caption"])}</div>'
        f"</div>"
    )


def render_glass_widgets(widgets: list[dict]) -> None:
    columns = st.columns(len(widgets))
    for column, widget in zip(columns, widgets):
        with column:
            markdown_html(glass_widget_html(widget))


# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------


def apply_chart_theme(fig: go.Figure, height: int = 410) -> go.Figure:
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(15,23,42,0.32)",
        font=dict(color="#e2e8f0"),
        margin=dict(l=10, r=10, t=30, b=10),
        height=height,
        xaxis_title=None,
        yaxis_title=None,
        legend_title=None,
    )
    fig.update_xaxes(showgrid=False, zeroline=False, color="#94a3b8")
    fig.update_yaxes(gridcolor="rgba(148, 163, 184, 0.14)", zeroline=False, color="#94a3b8")
    return fig


def build_plotly_figure(df: pd.DataFrame, x_col: str, y_col: str, chart_type: str) -> go.Figure:
    if chart_type == "Line":
        fig = px.line(df, x=x_col, y=y_col, markers=True)
    elif chart_type == "Area":
        fig = px.area(df, x=x_col, y=y_col)
    else:
        fig = px.bar(df, x=x_col, y=y_col)

    apply_chart_theme(fig)
    for trace in fig.data:
        if getattr(trace, "type", "") == "bar":
            trace.update(
                marker=dict(
                    color="#56ccf2",
                    line=dict(color="rgba(86, 204, 242, 0.45)", width=1),
                )
            )
        else:
            trace.update(marker=dict(color="#56ccf2"), line=dict(color="#56ccf2", width=3))
    return fig


def build_default_operations_figure() -> go.Figure:
    mock_df = pd.DataFrame(
        {
            "Window": ["08:00", "09:00", "10:00", "11:00", "12:00", "13:00"],
            "Throughput": [18, 24, 22, 31, 28, 36],
            "Quality": [92, 94, 93, 96, 95, 97],
        }
    )
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=mock_df["Window"],
            y=mock_df["Throughput"],
            mode="lines+markers",
            name="Workflow Throughput",
            line=dict(color="#56ccf2", width=3),
            marker=dict(size=7),
            fill="tozeroy",
            fillcolor="rgba(86, 204, 242, 0.12)",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=mock_df["Window"],
            y=mock_df["Quality"],
            mode="lines",
            name="Signal Quality",
            line=dict(color="#34d399", width=2, dash="dot"),
        )
    )
    apply_chart_theme(fig, height=420)
    fig.update_layout(
        plot_bgcolor="rgba(15,23,42,0.34)",
        margin=dict(l=10, r=10, t=24, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
    )
    return fig


# ---------------------------------------------------------------------------
# Workflow timeline
# ---------------------------------------------------------------------------


def latest_trace_by_step(trace: list[dict]) -> dict[str, dict]:
    latest = {}
    for item in trace:
        latest[item["step"]] = item
    return latest


def active_workflow_step(latest_by_step: dict[str, dict]) -> str | None:
    for step in reversed(WORKFLOW_STEPS):
        if latest_by_step.get(step):
            return step
    return None


def workflow_step_metadata(item: dict) -> str:
    telemetry_bits = []
    if item.get("model"):
        telemetry_bits.append(f'<span>{escape_html(item["model"])}</span>')
    if item.get("latency_ms") is not None:
        telemetry_bits.append(f'<span>{escape_html(item["latency_ms"])} ms</span>')
    if item.get("retries") is not None:
        telemetry_bits.append(f'<span>{escape_html(item["retries"])} retries</span>')
    return "".join(telemetry_bits or ["<span>Telemetry pending</span>"])


def workflow_node_html(step: str, item: dict, active_step: str | None, show_connector: bool) -> str:
    status = item.get("status", "idle")
    meta = STATUS_META.get(status, STATUS_META["pending"])
    step_info = STEP_META.get(step, {"title": step.title(), "caption": "Workflow step"})
    is_active = status == "active" or (step == active_step and status not in {"success", "error", "warning"})
    active_class = "active-agent" if is_active else ""
    connector = '<div class="workflow-connector"></div>' if show_connector else ""

    return (
        f'<div class="workflow-node-wrap">'
        f'<div class="workflow-node {active_class}">'
        f'<div class="workflow-node-top">'
        f"<div>"
        f'<div class="workflow-node-title">{escape_html(step_info["title"])}</div>'
        f'<div class="workflow-node-caption">{escape_html(step_info["caption"])}</div>'
        f"</div>"
        f'<div class="workflow-status-dot" style="--status-color:{meta["color"]};"></div>'
        f"</div>"
        f'<div class="workflow-node-status" style="color:{meta["color"]};">{meta["label"]}</div>'
        f'<div class="workflow-node-detail">{escape_html(item.get("detail", "Not started."))}</div>'
        f'<div class="workflow-node-metadata">{workflow_step_metadata(item)}</div>'
        f"</div>"
        f"{connector}"
        f"</div>"
    )


def workflow_timeline_html(trace: list[dict]) -> tuple[str, list[str]]:
    header = section_header_html(
        "AI Orchestration Workflow",
        "Enterprise workflow view from planning through execution, with agent status and telemetry context.",
    )
    if not trace:
        return header + '<div class="workflow-empty">Run a query to activate the workflow timeline.</div>', []

    latest = latest_trace_by_step(trace)
    active_step = active_workflow_step(latest)
    nodes = [
        workflow_node_html(
            step,
            latest.get(step, {"status": "idle", "detail": "Not started."}),
            active_step,
            index < len(WORKFLOW_STEPS) - 1,
        )
        for index, step in enumerate(WORKFLOW_STEPS)
    ]
    statuses = [latest.get(step, {"status": "pending"})["status"] for step in WORKFLOW_STEPS]
    return header + '<div class="workflow-rail-shell"><div class="workflow-rail">' + "".join(nodes) + "</div></div>", statuses


def build_workflow_chart(status_values: list[str]) -> go.Figure:
    fig = go.Figure(
        data=[
            go.Scatter(
                x=WORKFLOW_STEPS,
                y=[1] * len(WORKFLOW_STEPS),
                mode="lines+markers",
                marker=dict(
                    size=14,
                    color=[STATUS_META.get(status, STATUS_META["pending"])["color"] for status in status_values],
                    line=dict(color="#0f172a", width=2),
                ),
                line=dict(color="rgba(148, 163, 184, 0.22)", width=2),
                hovertemplate="%{x}<extra></extra>",
            )
        ]
    )
    fig.update_layout(
        height=90,
        margin=dict(l=10, r=10, t=0, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#e2e8f0"),
        xaxis=dict(showgrid=False, zeroline=False, visible=False),
        yaxis=dict(showgrid=False, zeroline=False, visible=False),
    )
    return fig


def render_workflow_timeline(trace: list[dict], chart_key: str | None = None) -> None:
    html, status_values = workflow_timeline_html(trace)
    markdown_html(html)
    if not trace:
        return

    workflow_chart_key = chart_key or f"workflow_chart_{st.session_state.get('live_render_seq', 0)}"
    st.plotly_chart(
        build_workflow_chart(status_values),
        width="stretch",
        config={"displayModeBar": False},
        key=workflow_chart_key,
    )


# ---------------------------------------------------------------------------
# Execution logs and telemetry
# ---------------------------------------------------------------------------


def live_execution_summary_html(question: str) -> str:
    return render_response_card(
        "Live Execution System",
        f"Autonomous orchestration is currently processing: {question}",
        "",
        tone="summary-module",
    )


def log_line_html(entry: dict) -> str:
    return (
        f'<div class="log-line">'
        f'<span class="log-time">{escape_html(entry["time"])}</span>'
        f'<span class="log-step">{escape_html(entry["step"])}</span>'
        f'<span class="log-message">{escape_html(entry["message"])}</span>'
        f"</div>"
    )


def execution_log_html(logs: list[dict]) -> str:
    log_items = "".join(log_line_html(entry) for entry in logs[-12:])
    if not log_items:
        log_items = '<div class="workflow-empty">Waiting for workflow events.</div>'
    return render_response_card(
        "Execution Log Stream",
        "Live operational events from the orchestration layer.",
        f'<div class="log-stream">{log_items}</div>',
        tone="default-module",
    )


def live_telemetry_items(telemetry: dict) -> list[tuple[str, object]]:
    return [
        ("Model", telemetry.get("model") or "Pending"),
        ("Prompt Tokens", f'{telemetry.get("prompt_tokens", 0):,}'),
        ("Completion Tokens", f'{telemetry.get("completion_tokens", 0):,}'),
        ("Total Tokens", f'{telemetry.get("total_tokens", 0):,}'),
        ("Latency", f'{telemetry.get("latency_ms", 0)} ms'),
        ("Cost", f'${telemetry.get("cost_usd", 0.0):.6f}'),
    ]


def progressive_telemetry_html(telemetry: dict) -> str:
    return render_response_card(
        "Progressive Telemetry",
        "Runtime usage and observability revealed as agents complete.",
        f'<div class="observability-grid">{metric_grid_html(live_telemetry_items(telemetry))}</div>',
        tone="observability-module",
    )


def render_live_execution_panel(
    question: str,
    trace: list[dict],
    logs: list[dict],
    telemetry: dict,
    chart_key: str | None = None,
) -> None:
    markdown_html(live_execution_summary_html(question))
    render_workflow_timeline(trace, chart_key=chart_key)

    left, right = st.columns([1.2, 0.8])
    with left:
        markdown_html(execution_log_html(logs))
    with right:
        markdown_html(progressive_telemetry_html(telemetry))


def render_telemetry_panel(telemetry: dict) -> None:
    markdown_html(
        section_header_html(
            "Model Telemetry",
            "Runtime visibility into token usage, latency, and model execution.",
        )
    )
    if not telemetry:
        st.info("Run a database query to see model telemetry.")
        return

    c1, c2, c3 = st.columns(3)
    c1.metric("Model", telemetry.get("model") or "Unavailable")
    c2.metric("Total Tokens", telemetry.get("total_tokens", 0))
    c3.metric("Latency", f'{telemetry.get("latency_ms", 0)} ms')

    c4, c5, c6 = st.columns(3)
    c4.metric("Prompt Tokens", telemetry.get("prompt_tokens", 0))
    c5.metric("Completion Tokens", telemetry.get("completion_tokens", 0))
    c6.metric("Estimated Cost", f'${telemetry.get("cost_usd", 0.0):.6f}')

    if not telemetry.get("usage_available", False):
        st.caption("Usage metadata was unavailable for one or more workflow steps.")


# ---------------------------------------------------------------------------
# Result, SQL, and dataset sections
# ---------------------------------------------------------------------------


def render_sql_and_results(sql: str, df: pd.DataFrame) -> None:
    markdown_html(
        section_header_html(
            "Analytics Workspace",
            "SQL generation and result exploration inside the same dark command surface.",
            class_name="workspace-shell",
        )
    )
    left, right = st.columns([1.05, 1.35])
    with left:
        markdown_html(
            section_header_html(
                "Generated SQL",
                "Inspectable query output from the AI workflow.",
                class_name="workspace-panel",
            )
        )
        st.code(sql or "-- CSV mode: no SQL generated", language="sql")

    with right:
        markdown_html(
            section_header_html(
                "Result Explorer",
                "Interactive preview of the returned dataset.",
                class_name="workspace-panel",
            )
        )
        if df.empty:
            st.warning("No data found for this query.")
        else:
            st.dataframe(df, width="stretch", height=360)


def render_sql_card(sql: str) -> None:
    if not sql:
        return
    markdown_html(
        section_header_html(
            "SQL Generation",
            "Collapsed by default to keep the workspace dense and operator-focused.",
            class_name="workspace-shell compact-shell",
        )
    )
    with st.expander("SQL Trace", expanded=False):
        st.code(sql, language="sql")


def render_result_table_card(df: pd.DataFrame, height: int = 240) -> None:
    if df.empty:
        return
    markdown_html(
        section_header_html(
            "Result Explorer",
            "Compact dataset preview inside the live analytics workspace.",
            class_name="workspace-shell compact-shell",
        )
    )
    st.dataframe(df, width="stretch", height=height)


# ---------------------------------------------------------------------------
# Recommendation and lower workspace cards
# ---------------------------------------------------------------------------


def render_recommendation_card(recommendations: list[str]) -> str:
    if not recommendations:
        recommendations = ["Run another question to unlock recommendations from a richer result set."]

    body = "".join(f'<div class="workspace-list-item">{escape_html(item)}</div>' for item in recommendations)
    return render_response_card(
        "AI Recommendations",
        "Suggested next actions based on the current result shape and workflow state.",
        body,
        tone="recommendation-module",
    )


def render_observability_card(telemetry: dict, trace: list[dict]) -> str:
    latest_status = trace[-1]["status"] if trace else "pending"
    latest_step = trace[-1]["step"] if trace else "Awaiting run"
    telemetry_bits = [
        ("Model", telemetry.get("model") or "Unavailable"),
        ("Total Tokens", f'{telemetry.get("total_tokens", 0):,}'),
        ("Latency", f'{telemetry.get("latency_ms", 0)} ms'),
        ("Cost", f'${telemetry.get("cost_usd", 0.0):.6f}'),
        ("Latest Step", latest_step),
        ("Status", latest_status.title()),
    ]
    return render_response_card(
        "Observability",
        "Operational telemetry across model usage, workflow state, and execution behavior.",
        f'<div class="observability-grid">{metric_grid_html(telemetry_bits)}</div>',
        tone="observability-module",
    )


def render_executive_summary(question: str, df: pd.DataFrame, exec_time: float | None, telemetry: dict) -> str:
    shape_text = f"{len(df):,} rows x {len(df.columns)} columns"
    lead_column = df.columns[0] if not df.empty else "N/A"
    exec_time_text = f"{exec_time:.2f}s" if exec_time is not None else "pending runtime"
    body = (
        f'<div class="summary-stat-strip">'
        f'<div class="summary-stat">'
        f'<div class="summary-stat-label">Question</div>'
        f'<div class="summary-stat-value">{escape_html(question or "Awaiting prompt")}</div>'
        f"</div>"
        f'<div class="summary-stat">'
        f'<div class="summary-stat-label">Dataset Shape</div>'
        f'<div class="summary-stat-value">{escape_html(shape_text)}</div>'
        f"</div>"
        f'<div class="summary-stat">'
        f'<div class="summary-stat-label">Primary Dimension</div>'
        f'<div class="summary-stat-value">{escape_html(lead_column)}</div>'
        f"</div>"
        f"</div>"
        f'<div class="executive-callout">'
        f"Latest workflow completed in {escape_html(exec_time_text)} with "
        f'{escape_html(f"{telemetry.get("total_tokens", 0):,}")} tokens processed. '
        f"The current dataset is ready for executive review, SQL inspection, and follow-up analysis."
        f"</div>"
    )
    return render_response_card(
        "Executive Insight Summary",
        "Top-level readout for operators, analysts, and decision-makers.",
        body,
        tone="summary-module",
    )


def render_activity_feed(items: list[dict]) -> str:
    body = "".join(
        (
            f'<div class="activity-item">'
            f'<div class="activity-dot {escape_html(item.get("tone", "live"))}"></div>'
            f'<div class="activity-copy">'
            f'<div class="activity-title">{escape_html(item["title"])}</div>'
            f'<div class="activity-subtitle">{escape_html(item["subtitle"])}</div>'
            f"</div>"
            f'<div class="activity-time">{escape_html(item["time"])}</div>'
            f"</div>"
        )
        for item in items
    )
    return render_response_card(
        "Recent AI Activity",
        "Operational feed showing the last meaningful system and copilot events.",
        body,
        tone="default-module",
    )


def render_agent_row(agents: list[dict]) -> str:
    pills = []
    for agent in agents:
        active_class = "agent-pill-active" if agent.get("active") else ""
        pills.append(
            f'<div class="agent-pill {active_class}">'
            f'<div class="agent-pill-top">'
            f'<span class="agent-pill-name">{escape_html(agent["name"])}</span>'
            f'<span class="agent-pill-status">{escape_html(agent["status"])}</span>'
            f"</div>"
            f'<div class="agent-pill-copy">{escape_html(agent["caption"])}</div>'
            f"</div>"
        )

    return render_response_card(
        "Active Orchestration Agents",
        "Default runtime posture across the orchestration stack before the next workflow begins.",
        f'<div class="agent-row">{"".join(pills)}</div>',
        tone="default-module",
    )


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------


def history_card_html(item: dict) -> str:
    return (
        f'<div class="timeline-card">'
        f'<div class="timeline-step">Question</div>'
        f'<div class="timeline-status" style="color:#f8fafc;">{escape_html(item["question"])}</div>'
        f'<div class="timeline-detail">Rows: {escape_html(item["rows"])}<br/>SQL: '
        f'<code>{escape_html(item["sql"] or "N/A")}</code></div>'
        f"</div>"
    )


def render_history(history: list[dict]) -> None:
    markdown_html(
        section_header_html(
            "Query History",
            "Recent workflow runs, generated SQL, and row counts.",
        )
    )
    if not history:
        st.info("No query history yet.")
        return

    for item in reversed(history[-10:]):
        markdown_html(history_card_html(item))
