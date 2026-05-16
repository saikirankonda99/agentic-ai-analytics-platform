from __future__ import annotations

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

STEP_META = {
    "planner": {"title": "Planner", "caption": "Intent routing"},
    "schema retrieval": {"title": "Schema", "caption": "Context retrieval"},
    "memory retrieval": {"title": "Memory", "caption": "History recall"},
    "sql generation": {"title": "SQL Agent", "caption": "Query synthesis"},
    "validation": {"title": "Validation", "caption": "Guardrail checks"},
    "reflection": {"title": "Reflection", "caption": "Self-correction"},
    "execution": {"title": "Execution", "caption": "Warehouse run"},
}


def render_hero() -> None:
    st.markdown(
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
        """,
        unsafe_allow_html=True,
    )


def render_sidebar() -> dict:
    with st.sidebar:
        st.markdown(
            """
            <div class="sidebar-brand">
                <p class="sidebar-brand-title">GenAI SQL Assistant</p>
                <div class="sidebar-brand-copy">Analytics operations cockpit for AI-native querying.</div>
            </div>
            """,
            unsafe_allow_html=True,
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
        for query in [
            "List all customers",
            "Top 10 customers by invoices",
            "Revenue by country",
            "Tracks with album and artist",
        ]:
            st.markdown(f'<div class="sample-query">{query}</div>', unsafe_allow_html=True)

        st.markdown("### CSV Upload")
        uploaded_file = st.file_uploader("Upload CSV", type=["csv"], label_visibility="collapsed")

        return {
            "nav": nav,
            "clear_chat": clear_chat,
            "show_schema": show_schema,
            "uploaded_file": uploaded_file,
        }


def render_prompt_launcher() -> str | None:
    st.markdown(
        """
        <div class="section-card compact-card">
            <div class="section-title">Prompt Launcher</div>
            <div class="section-subtitle">Launch a workflow from a recommended question or type your own below.</div>
        </div>
        """,
        unsafe_allow_html=True,
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


def render_chat_history(messages: list[dict]) -> None:
    st.markdown(
        """
        <div class="chat-card">
            <div class="section-title">AI Copilot Conversation</div>
            <div class="section-subtitle">Every workflow run is mirrored here so the reasoning trail stays visible.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if not messages:
        st.markdown(
            """
            <div class="response-card assistant-card">
                <div class="response-meta">AI Copilot</div>
                <div class="response-content">
                    Ask a question to populate the workspace with SQL, telemetry, workflow state, and executive
                    analytics.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    for msg in messages:
        role_class = "assistant-card" if msg["role"] == "assistant" else "user-card"
        role_label = "AI Copilot" if msg["role"] == "assistant" else "User Query"
        content = str(msg["content"]).replace("\n", "<br/>")
        st.markdown(
            f"""
            <div class="response-card {role_class}">
                <div class="response-meta">{role_label}</div>
                <div class="response-content">{content}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_kpi_cards(metrics: list[dict]) -> None:
    columns = st.columns(len(metrics))
    for column, metric in zip(columns, metrics):
        with column:
            st.markdown(
                f"""
                <div class="kpi-card">
                    <div class="kpi-label">{metric["label"]}</div>
                    <div class="kpi-value">{metric["value"]}</div>
                    <div class="kpi-delta">{metric["caption"]}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_glass_widgets(widgets: list[dict]) -> None:
    columns = st.columns(len(widgets))
    for column, widget in zip(columns, widgets):
        with column:
            badge = widget.get("badge")
            badge_html = f'<span class="status-pill">{badge}</span>' if badge else ""
            st.markdown(
                f"""
                <div class="glass-widget">
                    <div class="glass-widget-top">
                        <div class="glass-widget-label">{widget["label"]}</div>
                        {badge_html}
                    </div>
                    <div class="glass-widget-value">{widget["value"]}</div>
                    <div class="glass-widget-copy">{widget["caption"]}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_response_card(title: str, subtitle: str, body_html: str, tone: str = "default") -> None:
    st.markdown(
        f"""
        <div class="workspace-module {tone}">
            <div class="workspace-module-head">
                <div class="section-title">{title}</div>
                <div class="section-subtitle">{subtitle}</div>
            </div>

            <div class="workspace-module-body">
                {body_html}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

def render_command_bar() -> str | None:
    st.markdown(
        """
        <div class="workspace-shell compact-shell">
            <div class="section-title">Command Workspace</div>
            <div class="section-subtitle">Submit a question and keep orchestration anchored to the analytics workspace.</div>
        </div>
        """,
        unsafe_allow_html=True,
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


def build_plotly_figure(df: pd.DataFrame, x_col: str, y_col: str, chart_type: str) -> go.Figure:
    if chart_type == "Line":
        fig = px.line(df, x=x_col, y=y_col, markers=True)
    elif chart_type == "Area":
        fig = px.area(df, x=x_col, y=y_col)
    else:
        fig = px.bar(df, x=x_col, y=y_col)

    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(15,23,42,0.32)",
        font=dict(color="#e2e8f0"),
        margin=dict(l=10, r=10, t=30, b=10),
        height=410,
        xaxis_title=None,
        yaxis_title=None,
        legend_title=None,
    )
    fig.update_xaxes(
        showgrid=False,
        zeroline=False,
        color="#94a3b8",
    )
    fig.update_yaxes(
        gridcolor="rgba(148, 163, 184, 0.14)",
        zeroline=False,
        color="#94a3b8",
    )
    if fig.data:
        for trace in fig.data:
            if getattr(trace, "type", "") == "bar":
                trace.update(
                    marker=dict(
                        color="#56ccf2",
                        line=dict(color="rgba(86, 204, 242, 0.45)", width=1),
                    )
                )
            else:
                trace.update(
                    marker=dict(color="#56ccf2"),
                    line=dict(color="#56ccf2", width=3),
                )
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
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(15,23,42,0.34)",
        font=dict(color="#e2e8f0"),
        margin=dict(l=10, r=10, t=24, b=10),
        height=420,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
    )
    fig.update_xaxes(showgrid=False, zeroline=False, color="#94a3b8")
    fig.update_yaxes(gridcolor="rgba(148, 163, 184, 0.14)", zeroline=False, color="#94a3b8")
    return fig


def render_workflow_timeline(trace: list[dict], chart_key: str | None = None) -> None:
    st.markdown(
        """
        <div class="section-card compact-card">
            <div class="section-title">AI Orchestration Workflow</div>
            <div class="section-subtitle">Enterprise workflow view from planning through execution, with agent status and telemetry context.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    ordered_steps = [
        "planner",
        "schema retrieval",
        "memory retrieval",
        "sql generation",
        "validation",
        "reflection",
        "execution",
    ]

    latest_by_step = {}
    for item in trace:
        latest_by_step[item["step"]] = item

    if not trace:
        st.markdown('<div class="workflow-empty">Run a query to activate the workflow timeline.</div>', unsafe_allow_html=True)
        return

    status_values = [latest_by_step.get(step, {"status": "pending"})["status"] for step in ordered_steps]
    active_step = None
    for step in reversed(ordered_steps):
        if latest_by_step.get(step):
            active_step = step
            break

    workflow_html = ['<div class="workflow-rail-shell"><div class="workflow-rail">']
    for index, step in enumerate(ordered_steps):
        item = latest_by_step.get(step, {"status": "idle", "detail": "Not started."})
        meta = STATUS_META.get(item["status"], STATUS_META["pending"])
        step_info = STEP_META.get(step, {"title": step.title(), "caption": "Workflow step"})
        is_active = item["status"] == "active" or (step == active_step and item["status"] not in {"success", "error", "warning"})
        connector = ""
        if index < len(ordered_steps) - 1:
            connector = '<div class="workflow-connector"></div>'

        latency = item.get("latency_ms")
        retries = item.get("retries")
        model = item.get("model")

        telemetry_bits = []
        if model:
            telemetry_bits.append(f"<span>{model}</span>")
        if latency is not None:
            telemetry_bits.append(f"<span>{latency} ms</span>")
        if retries is not None:
            telemetry_bits.append(f"<span>{retries} retries</span>")
        if not telemetry_bits:
            telemetry_bits.append("<span>Telemetry pending</span>")

        workflow_html.append(
            f"""
            <div class="workflow-node-wrap">
                <div class="workflow-node {'active-agent' if is_active else ''}">
                    <div class="workflow-node-top">
                        <div>
                            <div class="workflow-node-title">{step_info["title"]}</div>
                            <div class="workflow-node-caption">{step_info["caption"]}</div>
                        </div>
                        <div class="workflow-status-dot" style="--status-color:{meta["color"]};"></div>
                    </div>
                    <div class="workflow-node-status" style="color:{meta["color"]};">{meta["label"]}</div>
                    <div class="workflow-node-detail">{item["detail"]}</div>
                    <div class="workflow-node-metadata">{''.join(telemetry_bits)}</div>
                </div>
                {connector}
            </div>
            """
        )
    workflow_html.append("</div></div>")
    st.markdown("".join(workflow_html), unsafe_allow_html=True)

    fig = go.Figure(
        data=[
            go.Scatter(
                x=ordered_steps,
                y=[1] * len(ordered_steps),
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
    workflow_chart_key = (
        chart_key
        or f"workflow_chart_{st.session_state.get('live_render_seq', 0)}"
    )

    st.plotly_chart(
        fig,
        width="stretch",
        config={"displayModeBar": False},
        key=workflow_chart_key,
    )


def render_live_execution_panel(
    question: str,
    trace: list[dict],
    logs: list[dict],
    telemetry: dict,
    chart_key: str | None = None,
) -> None:
    st.markdown(
        f"""
        <div class="workspace-module summary-module">
            <div class="workspace-module-head">
                <div class="section-title">Live Execution System</div>
                <div class="section-subtitle">Autonomous orchestration is currently processing: {question}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    render_workflow_timeline(trace, chart_key=chart_key)

    left, right = st.columns([1.2, 0.8])
    with left:
        log_items = "".join(
            [
                f"""
                <div class="log-line">
                    <span class="log-time">{entry["time"]}</span>
                    <span class="log-step">{entry["step"]}</span>
                    <span class="log-message">{entry["message"]}</span>
                </div>
                """
                for entry in logs[-12:]
            ]
        ) or '<div class="workflow-empty">Waiting for workflow events.</div>'
        st.markdown(
            """
            <div class="workspace-module default-module">
                <div class="workspace-module-head">
                    <div class="section-title">Execution Log Stream</div>
                    <div class="section-subtitle">
                        Live operational events from the orchestration layer.
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown(
            f'<div class="log-stream">{log_items}</div>',
            unsafe_allow_html=True,
        )
    with right:
        telemetry_items = [
            ("Model", telemetry.get("model") or "Pending"),
            ("Prompt Tokens", f'{telemetry.get("prompt_tokens", 0):,}'),
            ("Completion Tokens", f'{telemetry.get("completion_tokens", 0):,}'),
            ("Total Tokens", f'{telemetry.get("total_tokens", 0):,}'),
            ("Latency", f'{telemetry.get("latency_ms", 0)} ms'),
            ("Cost", f'${telemetry.get("cost_usd", 0.0):.6f}'),
        ]

        telemetry_html = "".join(
            [
                f"""
                <div class="observability-metric">
                    <div class="observability-label">{label}</div>
                    <div class="observability-value">{value}</div>
                </div>
                """
                for label, value in telemetry_items
            ]
        )

        st.markdown(
            """
            <div class="workspace-module observability-module">
                <div class="workspace-module-head">
                    <div class="section-title">Progressive Telemetry</div>
                    <div class="section-subtitle">
                        Runtime usage and observability revealed as agents complete.
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown(
            f'<div class="observability-grid">{telemetry_html}</div>',
            unsafe_allow_html=True,
        )


def render_sql_and_results(sql: str, df: pd.DataFrame) -> None:
    st.markdown(
        """
        <div class="workspace-shell">
            <div class="section-title">Analytics Workspace</div>
            <div class="section-subtitle">SQL generation and result exploration inside the same dark command surface.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    left, right = st.columns([1.05, 1.35])
    with left:
        st.markdown(
            """
            <div class="workspace-panel">
                <div class="section-title">Generated SQL</div>
                <div class="section-subtitle">Inspectable query output from the AI workflow.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.code(sql or "-- CSV mode: no SQL generated", language="sql")

    with right:
        st.markdown(
            """
            <div class="workspace-panel">
                <div class="section-title">Result Explorer</div>
                <div class="section-subtitle">Interactive preview of the returned dataset.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if df.empty:
            st.warning("No data found for this query.")
        else:
            st.dataframe(df, width="stretch", height=360)


def render_sql_card(sql: str) -> None:
    if not sql:
        return
    st.markdown(
        """
        <div class="workspace-shell compact-shell">
            <div class="section-title">SQL Generation</div>
            <div class="section-subtitle">Collapsed by default to keep the workspace dense and operator-focused.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    with st.expander("SQL Trace", expanded=False):
        st.code(sql, language="sql")


def render_result_table_card(df: pd.DataFrame, height: int = 240) -> None:
    if df.empty:
        return
    st.markdown(
        """
        <div class="workspace-shell compact-shell">
            <div class="section-title">Result Explorer</div>
            <div class="section-subtitle">Compact dataset preview inside the live analytics workspace.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.dataframe(df, width="stretch", height=height)


def render_recommendation_card(recommendations: list[str]) -> None:
    if not recommendations:
        recommendations = ["Run another question to unlock recommendations from a richer result set."]

    body = "".join([f'<div class="workspace-list-item">{item}</div>' for item in recommendations])
    render_response_card(
        "AI Recommendations",
        "Suggested next actions based on the current result shape and workflow state.",
        body,
        tone="recommendation-module",
    )


def render_observability_card(telemetry: dict, trace: list[dict]) -> None:
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
    body = "".join(
        [
            f"""
            <div class="observability-metric">
                <div class="observability-label">{label}</div>
                <div class="observability-value">{value}</div>
            </div>
            """
            for label, value in telemetry_bits
        ]
    )
    render_response_card(
        "Observability",
        "Operational telemetry across model usage, workflow state, and execution behavior.",
        f'<div class="observability-grid">{body}</div>',
        tone="observability-module",
    )


def render_executive_summary(question: str, df: pd.DataFrame, exec_time: float | None, telemetry: dict) -> None:
    shape_text = f"{len(df):,} rows x {len(df.columns)} columns"
    lead_column = df.columns[0] if not df.empty else "N/A"
    body = f"""
    <div class="summary-stat-strip">
        <div class="summary-stat">
            <div class="summary-stat-label">Question</div>
            <div class="summary-stat-value">{question or "Awaiting prompt"}</div>
        </div>
        <div class="summary-stat">
            <div class="summary-stat-label">Dataset Shape</div>
            <div class="summary-stat-value">{shape_text}</div>
        </div>
        <div class="summary-stat">
            <div class="summary-stat-label">Primary Dimension</div>
            <div class="summary-stat-value">{lead_column}</div>
        </div>
    </div>
    <div class="executive-callout">
        Latest workflow completed in {exec_time:.2f}s with {telemetry.get("total_tokens", 0):,} tokens processed.
        The current dataset is ready for executive review, SQL inspection, and follow-up analysis.
    </div>
    """
    render_response_card(
        "Executive Insight Summary",
        "Top-level readout for operators, analysts, and decision-makers.",
        body,
        tone="summary-module",
    )


def render_activity_feed(items: list[dict]) -> None:
    body = "".join(
        [
            f"""
            <div class="activity-item">
                <div class="activity-dot {item.get("tone", "live")}"></div>
                <div class="activity-copy">
                    <div class="activity-title">{item["title"]}</div>
                    <div class="activity-subtitle">{item["subtitle"]}</div>
                </div>
                <div class="activity-time">{item["time"]}</div>
            </div>
            """
            for item in items
        ]
    )
    render_response_card(
        "Recent AI Activity",
        "Operational feed showing the last meaningful system and copilot events.",
        body,
        tone="default-module",
    )


def render_agent_row(agents: list[dict]) -> None:
    body = '<div class="agent-row">' + "".join(
        [
            f"""
            <div class="agent-pill {'agent-pill-active' if agent.get("active") else ''}">
                <div class="agent-pill-top">
                    <span class="agent-pill-name">{agent["name"]}</span>
                    <span class="agent-pill-status">{agent["status"]}</span>
                </div>
                <div class="agent-pill-copy">{agent["caption"]}</div>
            </div>
            """
            for agent in agents
        ]
    ) + "</div>"
    render_response_card(
        "Active Orchestration Agents",
        "Default runtime posture across the orchestration stack before the next workflow begins.",
        body,
        tone="default-module",
    )


def render_telemetry_panel(telemetry: dict) -> None:
    st.markdown(
        """
        <div class="section-card compact-card">
            <div class="section-title">Model Telemetry</div>
            <div class="section-subtitle">Runtime visibility into token usage, latency, and model execution.</div>
        </div>
        """,
        unsafe_allow_html=True,
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


def render_history(history: list[dict]) -> None:
    st.markdown(
        """
        <div class="section-card compact-card">
            <div class="section-title">Query History</div>
            <div class="section-subtitle">Recent workflow runs, generated SQL, and row counts.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if not history:
        st.info("No query history yet.")
        return

    for item in reversed(history[-10:]):
        st.markdown(
            f"""
            <div class="timeline-card">
                <div class="timeline-step">Question</div>
                <div class="timeline-status" style="color:#f8fafc;">{item["question"]}</div>
                <div class="timeline-detail">Rows: {item["rows"]}<br/>SQL: <code>{item["sql"] or "N/A"}</code></div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_footer() -> None:
    st.markdown(
        """
        <div class="footer-note">
            Built with Streamlit and OpenAI for AI-native analytics workflows.
        </div>
        """,
        unsafe_allow_html=True,
    )
