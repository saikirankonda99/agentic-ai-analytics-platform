from __future__ import annotations

from html import escape
import re
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
    "skipped": {"label": "Skipped", "color": "#94a3b8"},
    "pending": {"label": "Idle", "color": "#64748b"},
}

WORKFLOW_STEPS = [
    "planner",
    "schema retrieval",
    "memory retrieval",
    "monitoring",
    "sql generation",
    "validation",
    "reflection",
    "execution",
    "autonomous insight",
    "investigation",
    "briefing",
    "insight",
]

STEP_META = {
    "planner": {"title": "Planner", "caption": "Intent routing"},
    "schema retrieval": {"title": "Schema", "caption": "Context retrieval"},
    "memory retrieval": {"title": "Memory", "caption": "History recall"},
    "monitoring": {"title": "Monitoring", "caption": "Scheduled KPI checks"},
    "sql generation": {"title": "SQL Agent", "caption": "Query synthesis"},
    "validation": {"title": "Validation", "caption": "Guardrail checks"},
    "reflection": {"title": "Reflection", "caption": "Self-correction"},
    "execution": {"title": "Execution", "caption": "Warehouse run"},
    "autonomous insight": {"title": "Insight Agent", "caption": "Signal detection"},
    "investigation": {"title": "Investigation", "caption": "Root-cause drill-down"},
    "briefing": {"title": "Briefing", "caption": "Executive summary"},
    "insight": {"title": "Insight", "caption": "Executive readout"},
}

SAMPLE_PROMPTS = [
    "List all customers",
    "Top 10 customers by invoices",
    "Revenue by country",
    "Tracks with album and artist",
]

ONBOARDING_LABELS = {
    "workspace_intro": "Workspace",
    "sample_dataset": "Dataset",
    "first_query": "First Query",
    "results_reviewed": "Review",
    "export_completed": "Export",
}


# ---------------------------------------------------------------------------
# HTML primitives
# ---------------------------------------------------------------------------


def escape_html(value: object) -> str:
    return escape("" if value is None else str(value), quote=True)


def markdown_html(html: str) -> None:
    st.markdown(html, unsafe_allow_html=True)


def next_plotly_key(scope: str) -> str:
    st.session_state.plotly_key_seq = st.session_state.get("plotly_key_seq", 0) + 1
    run_id = st.session_state.get("run_id", "default")
    return f"{scope}_{run_id}_{st.session_state.plotly_key_seq}"


def test_id(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "workspace-section"


def section_header_html(title: str, subtitle: str, class_name: str = "section-card compact-card") -> str:
    return (
        f'<div class="{class_name}" data-testid="{test_id(title)}">'
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
        f'<div class="workspace-module {tone}" data-testid="{test_id(title)}">'
        f'<div class="workspace-module-head">'
        f'<div class="section-title">{escape_html(title)}</div>'
        f'<div class="section-subtitle">{escape_html(subtitle)}</div>'
        f"</div>"
        f"{response_body_html(body_html)}"
        f"</div>"
    )


def render_onboarding_card(onboarding: dict | None, steps: list[dict]) -> str:
    onboarding = onboarding or {}
    step_state = onboarding.get("steps", {})
    total = onboarding.get("total_count") or len(steps) or 1
    completed = onboarding.get("completed_count", 0)
    percent = onboarding.get("percent", round((completed / total) * 100))
    body = (
        f'<div class="onboarding-progress-shell">'
        f'<div class="onboarding-progress-track"><span style="width:{max(0, min(percent, 100))}%;"></span></div>'
        f'<div class="workspace-body-copy">{escape_html(completed)} of {escape_html(total)} onboarding steps complete.</div>'
        f"</div>"
    )
    body += '<div class="onboarding-step-grid">'
    for item in steps:
        step_id = item.get("step_id", "")
        done = bool(step_state.get(step_id))
        state_class = " onboarding-step-done" if done else ""
        state_label = "Done" if done else "Next"
        body += (
            f'<div class="onboarding-step{state_class}">'
            f'<div class="observability-label">{escape_html(state_label)}</div>'
            f'<div class="onboarding-step-title">{escape_html(item.get("label") or ONBOARDING_LABELS.get(step_id, step_id))}</div>'
            f'<div class="onboarding-step-copy">{escape_html(item.get("description", ""))}</div>'
            f"</div>"
        )
    body += "</div>"
    return render_response_card(
        "Workspace Onboarding",
        "Guided setup for the sample dataset, first query, result review, and exports.",
        body,
        tone="summary-module",
    )


def render_empty_state_card(title: str, subtitle: str, actions: list[str]) -> str:
    action_html = "".join(f'<div class="workspace-list-item">{escape_html(action)}</div>' for action in actions)
    return render_response_card(
        title,
        subtitle,
        action_html or '<div class="workspace-body-copy">No action is available yet.</div>',
        tone="default-module",
    )


def render_quick_actions_card(actions: list[dict]) -> str:
    body = "".join(
        (
            f'<div class="quick-action-item">'
            f'<div class="quick-action-label">{escape_html(item.get("label", ""))}</div>'
            f'<div class="quick-action-copy">{escape_html(item.get("caption", ""))}</div>'
            f"</div>"
        )
        for item in actions
    )
    return render_response_card(
        "Quick Actions",
        "Common operator paths for fast workspace recovery and exploration.",
        f'<div class="quick-action-grid">{body}</div>',
        tone="recommendation-module",
    )


def render_saved_assets_card(memory: dict | None) -> str:
    memory = memory or {}
    shared_count = sum(
        1
        for collection in ("query_bookmarks", "investigations", "bookmarks", "pinned_investigations", "saved_reports")
        for item in memory.get(collection, [])
        if item.get("visibility") == "team"
    )
    items = [
        ("Saved Queries", len(memory.get("query_bookmarks", []))),
        ("Saved Investigations", len(memory.get("investigations", []))),
        ("Pinned Investigations", len(memory.get("pinned_investigations", []))),
        ("Saved Reports", len(memory.get("saved_reports", []))),
        ("Shared Items", shared_count),
        ("Recent Activities", len(memory.get("recent_activity", []))),
        ("Sessions", len(memory.get("sessions", []))),
    ]
    return render_response_card(
        "Workspace Continuity",
        "Persistent assets restored for the active workspace.",
        f'<div class="observability-grid">{metric_grid_html(items)}</div>',
        tone="observability-module",
    )


def render_recovery_guidance_card(telemetry: dict | None, validation: dict | None, recovery: dict | None) -> str:
    telemetry = telemetry or {}
    validation = validation or {}
    recovery = recovery or {}
    latest_error = next(
        (item for item in reversed(telemetry.get("steps", [])) if item.get("error_type") or item.get("error_message")),
        {},
    )
    hints = []
    if latest_error:
        hints.append(f'OpenAI request issue: {latest_error.get("error_message", "request failed")}')
        hints.append("Retry the workflow after checking model availability, API key configuration, and request size.")
    if validation.get("warnings"):
        hints.extend([f"SQL validation: {item}" for item in validation.get("warnings", [])[:3]])
    if recovery.get("message"):
        hints.append(recovery["message"])
    if not hints:
        hints = [
            "No active recovery action is required.",
            "If a connector fails, validate credentials and schema access from the API workspace.",
        ]
    body = "".join(f'<div class="workspace-list-item">{escape_html(item)}</div>' for item in hints)
    return render_response_card(
        "Recovery Guidance",
        "Plain-language next steps for connector, SQL validation, and OpenAI runtime issues.",
        body,
        tone="insight-module" if latest_error or validation.get("warnings") else "default-module",
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
        <div class="enterprise-hero">
            <div>
                <div class="hero-eyebrow">Enterprise AI Analytics Workspace</div>
                <h1 class="hero-title">Agentic analytics command center</h1>
                <p class="hero-copy">
                    Ask in natural language, inspect governed SQL, monitor orchestration, and publish executive-ready
                    insights from one production workspace.
                </p>
            </div>
            <div class="hero-badges">
                <span class="hero-badge">Multi-agent</span>
                <span class="hero-badge">Telemetry-ready</span>
                <span class="hero-badge">RBAC-aware</span>
                <span class="hero-badge">Workflow-native</span>
            </div>
        </div>
        """
    )


def render_top_navigation(active_nav: str = "Overview") -> str:
    nav_options = ["Overview", "Operations", "Copilot", "Investigations", "Monitoring", "Agents", "API", "History"]
    if active_nav not in nav_options:
        active_nav = "Overview"

    markdown_html(
        """
        <div class="top-nav-shell">
            <div>
                <div class="top-nav-title">Analytics Operations Workspace</div>
                <div class="top-nav-subtitle">Unified workspace for query execution, orchestration, monitoring, and audit trails.</div>
            </div>
        </div>
        """
    )
    return st.radio(
        "Primary navigation",
        nav_options,
        index=nav_options.index(active_nav),
        horizontal=True,
        label_visibility="collapsed",
        key="top_navigation",
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

        with st.expander("Orchestration Controls", expanded=True):
            clear_chat = st.button("Clear session", width="stretch")
            show_schema = st.toggle("Show database schema", value=False)

        with st.expander("Workspace Context", expanded=True):
            current_identity = st.session_state.get("user_identity") or {}
            workspace_scope = st.radio(
                "Workspace scope",
                ["Personal", "Shared team"],
                index=1 if current_identity.get("workspace_scope") == "team" else 0,
                horizontal=True,
            )
            workspace_user = st.text_input("User", value=current_identity.get("user_id", "local.user"))
            workspace_team = st.text_input("Team", value=current_identity.get("team_id", "default-team"))
            workspace_role = st.selectbox(
                "Role",
                ["admin", "analyst", "viewer"],
                index=["admin", "analyst", "viewer"].index(current_identity.get("role", "admin"))
                if current_identity.get("role", "admin") in ["admin", "analyst", "viewer"]
                else 0,
            )

        with st.expander("Launch Templates", expanded=False):
            for query in SAMPLE_PROMPTS:
                markdown_html(f'<div class="sample-query">{escape_html(query)}</div>')

        with st.expander("Dataset Upload", expanded=False):
            uploaded_file = st.file_uploader("Upload CSV", type=["csv"], label_visibility="collapsed")

        with st.expander("Scheduled Monitoring", expanded=False):
            monitoring_enabled = st.toggle(
                "Enable scheduled checks",
                value=st.session_state.get("monitoring_config", {}).get("enabled", False),
            )
            monitoring_targets = st.multiselect(
                "KPI targets",
                ["revenue", "customers", "orders", "growth", "anomalies"],
                default=st.session_state.get("monitoring_config", {}).get(
                    "targets",
                    ["revenue", "customers", "orders", "growth", "anomalies"],
                ),
            )
            monitoring_interval = st.selectbox(
                "Cadence",
                [15, 30, 60, 240, 1440],
                index=[15, 30, 60, 240, 1440].index(
                    st.session_state.get("monitoring_config", {}).get("interval_minutes", 60)
                    if st.session_state.get("monitoring_config", {}).get("interval_minutes", 60)
                    in [15, 30, 60, 240, 1440]
                    else 60
                ),
                format_func=lambda value: f"{value} min" if value < 1440 else "Daily",
            )
            run_monitoring = st.button("Run scheduled check", width="stretch")

        return {
            "nav": st.session_state.get("top_navigation", "Overview"),
            "clear_chat": clear_chat,
            "show_schema": show_schema,
            "uploaded_file": uploaded_file,
            "workspace_user": workspace_user,
            "workspace_team": workspace_team,
            "workspace_role": workspace_role,
            "workspace_scope": workspace_scope,
            "monitoring_enabled": monitoring_enabled,
            "monitoring_targets": monitoring_targets,
            "monitoring_interval": monitoring_interval,
            "run_monitoring": run_monitoring,
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
    if item.get("timestamp"):
        telemetry_bits.append(f'<span>{escape_html(str(item["timestamp"])[11:19] or item["timestamp"])}</span>')
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
    terminal_states = {"success", "error", "warning", "skipped"}
    is_active = status == "active" or (step == active_step and status not in terminal_states)
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


def orchestration_status_summary(trace: list[dict], telemetry: dict | None, is_executing: bool = False) -> list[dict]:
    telemetry = telemetry or {}
    latest = trace[-1] if trace else {}
    failed = any(item.get("status") == "error" for item in trace)
    warnings = sum(1 for item in trace if item.get("status") in {"warning", "retry"})
    completed = sum(1 for item in trace if item.get("status") == "success")
    status = "Running" if is_executing else "Failed" if failed else "Ready" if trace else "Standby"
    status_tone = "active" if is_executing else "error" if failed else "success" if trace else "idle"
    return [
        {
            "label": "Orchestration",
            "value": status,
            "caption": latest.get("detail") or "Awaiting the next workflow run.",
            "tone": status_tone,
        },
        {
            "label": "Active Phase",
            "value": STEP_META.get(latest.get("step"), {}).get("title", "No active phase"),
            "caption": latest.get("timestamp", "Runtime not started"),
            "tone": latest.get("status", "idle"),
        },
        {
            "label": "Agent Checks",
            "value": f"{completed}/{len(WORKFLOW_STEPS)}",
            "caption": f"{warnings} warning signals across the current trace.",
            "tone": "warning" if warnings else "success" if completed else "idle",
        },
        {
            "label": "Governance",
            "value": f'${telemetry.get("cost_usd", 0.0):.4f}',
            "caption": f'{telemetry.get("total_tokens", 0):,} tokens processed.',
            "tone": "success" if telemetry else "idle",
        },
    ]


def render_orchestration_status_badges(trace: list[dict], telemetry: dict | None, is_executing: bool = False) -> str:
    badges = []
    for item in orchestration_status_summary(trace, telemetry, is_executing):
        tone = item.get("tone", "idle")
        meta = STATUS_META.get(tone, STATUS_META.get("pending"))
        badges.append(
            f'<div class="orchestration-badge">'
            f'<div class="orchestration-badge-top">'
            f'<span class="orchestration-badge-label">{escape_html(item["label"])}</span>'
            f'<span class="orchestration-badge-dot" style="--status-color:{meta["color"]};"></span>'
            f"</div>"
            f'<div class="orchestration-badge-value">{escape_html(item["value"])}</div>'
            f'<div class="orchestration-badge-caption">{escape_html(item["caption"])}</div>'
            f"</div>"
        )
    return '<div class="orchestration-badge-grid">' + "".join(badges) + "</div>"


def render_workflow_timeline_cards(trace: list[dict]) -> str:
    latest = latest_trace_by_step(trace)
    active_step = active_workflow_step(latest)
    cards = []
    for step in WORKFLOW_STEPS:
        item = latest.get(step, {"status": "pending", "detail": "Not started."})
        status = item.get("status", "pending")
        meta = STATUS_META.get(status, STATUS_META["pending"])
        step_info = STEP_META.get(step, {"title": step.title(), "caption": "Workflow step"})
        active_class = " timeline-card-active" if step == active_step and status not in {"success", "error", "warning", "skipped"} else ""
        cards.append(
            f'<div class="workflow-timeline-card{active_class}">'
            f'<div class="workflow-timeline-card-marker" style="--status-color:{meta["color"]};"></div>'
            f'<div class="workflow-timeline-card-copy">'
            f'<div class="workflow-timeline-card-title">{escape_html(step_info["title"])}</div>'
            f'<div class="workflow-timeline-card-caption">{escape_html(step_info["caption"])}</div>'
            f'<div class="workflow-timeline-card-detail">{escape_html(item.get("detail", "Not started."))}</div>'
            f"</div>"
            f'<div class="workflow-timeline-card-status" style="color:{meta["color"]};">{escape_html(meta["label"])}</div>'
            f"</div>"
        )
    return render_response_card(
        "Workflow Timeline Cards",
        "Card-based lifecycle view for each orchestration phase and agent handoff.",
        f'<div class="workflow-timeline-card-grid">{"".join(cards)}</div>',
        tone="default-module",
    )


def active_agent_states(trace: list[dict], telemetry: dict | None, is_executing: bool = False) -> list[dict]:
    telemetry = telemetry or {}
    latest = latest_trace_by_step(trace)
    agent_map = [
        ("Planner", "planner", "Intent routing and task decomposition."),
        ("Schema Agent", "schema retrieval", "Semantic and database context retrieval."),
        ("Memory Agent", "memory retrieval", "Workspace and conversation recall."),
        ("SQL Agent", "sql generation", "SQL synthesis and refinement."),
        ("Validator", "validation", "Guardrails, permissions, and query checks."),
        ("Execution Agent", "execution", "Warehouse execution and result shaping."),
        ("Insight Agent", "autonomous insight", "Anomaly, trend, and concentration detection."),
        ("Investigator", "investigation", "Autonomous follow-up probes."),
    ]
    active_step = active_workflow_step(latest)
    states = []
    for name, step, caption in agent_map:
        item = latest.get(step, {})
        status = item.get("status", "ready" if not trace else "idle")
        if is_executing and step == active_step:
            status = "active"
        states.append(
            {
                "name": name,
                "status": STATUS_META.get(status, {"label": status.title()})["label"],
                "caption": item.get("detail") or caption,
                "step": step,
                "active": status == "active",
                "tone": status,
                "model": item.get("model") or telemetry.get("model") or "standby",
                "latency": item.get("latency_ms"),
            }
        )
    return states


def render_active_agent_monitoring(trace: list[dict], telemetry: dict | None, is_executing: bool = False) -> str:
    panels = []
    for agent in active_agent_states(trace, telemetry, is_executing):
        meta = STATUS_META.get(agent.get("tone"), STATUS_META["pending"])
        latency = f'{agent["latency"]} ms' if agent.get("latency") is not None else "Latency pending"
        active_class = " agent-monitor-active" if agent.get("active") else ""
        panels.append(
            f'<div class="agent-monitor-panel{active_class}">'
            f'<div class="agent-monitor-head">'
            f'<div>'
            f'<div class="agent-monitor-name">{escape_html(agent["name"])}</div>'
            f'<div class="agent-monitor-step">{escape_html(agent["step"])}</div>'
            f"</div>"
            f'<span class="agent-monitor-status" style="--status-color:{meta["color"]};">{escape_html(agent["status"])}</span>'
            f"</div>"
            f'<div class="agent-monitor-caption">{escape_html(agent["caption"])}</div>'
            f'<div class="agent-monitor-meta">'
            f'<span>{escape_html(agent["model"])}</span>'
            f'<span>{escape_html(latency)}</span>'
            f"</div>"
            f"</div>"
        )
    return render_response_card(
        "Active Agent Monitoring",
        "Operational status panels for the agents participating in the current analytics workflow.",
        f'<div class="agent-monitor-grid">{"".join(panels)}</div>',
        tone="observability-module",
    )


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

    workflow_chart_key = chart_key or next_plotly_key("workflow_chart")
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
    items = [
        ("Model", telemetry.get("model") or "Pending"),
        ("Prompt Tokens", f'{telemetry.get("prompt_tokens", 0):,}'),
        ("Completion Tokens", f'{telemetry.get("completion_tokens", 0):,}'),
        ("Total Tokens", f'{telemetry.get("total_tokens", 0):,}'),
        ("Latency", f'{telemetry.get("latency_ms", 0)} ms'),
        ("Cost", f'${telemetry.get("cost_usd", 0.0):.6f}'),
    ]
    latest_error = next(
        (item for item in reversed(telemetry.get("steps", [])) if item.get("error_type") or item.get("error_message")),
        {},
    )
    if latest_error:
        items.extend(
            [
                ("OpenAI Error", latest_error.get("error_type", "Unknown")),
                ("Attempt", f'{latest_error.get("error_attempt", "?")}/{latest_error.get("error_max_attempts", "?")}'),
            ]
        )
    return items


def progressive_telemetry_html(telemetry: dict) -> str:
    return render_response_card(
        "Progressive Telemetry",
        "Runtime usage and observability revealed as agents complete.",
        f'<div class="observability-grid">{metric_grid_html(live_telemetry_items(telemetry))}</div>',
        tone="observability-module",
    )


def assistant_stream_html(streams: dict | None) -> str:
    active_streams = {key: value for key, value in (streams or {}).items() if value}
    if not active_streams:
        return ""

    body = "".join(
        (
            f'<div class="workspace-list-item">'
            f'<div class="observability-label">{escape_html(phase)}</div>'
            f'<div class="workspace-body-copy">{escape_html(content).replace(chr(10), "<br/>")}</div>'
            f"</div>"
        )
        for phase, content in active_streams.items()
    )
    return render_response_card(
        "Streaming Assistant Output",
        "Partial model responses are displayed as tokens arrive.",
        body,
        tone="insight-module",
    )


def render_live_execution_panel(
    question: str,
    trace: list[dict],
    logs: list[dict],
    telemetry: dict,
    chart_key: str | None = None,
    assistant_streams: dict | None = None,
) -> None:
    markdown_html(live_execution_summary_html(question))
    render_workflow_timeline(trace, chart_key=chart_key)

    left, right = st.columns([1.2, 0.8])
    with left:
        markdown_html(execution_log_html(logs))
        stream_html = assistant_stream_html(assistant_streams)
        if stream_html:
            markdown_html(stream_html)
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
    latest_error = next(
        (item for item in reversed(telemetry.get("steps", [])) if item.get("error_type") or item.get("error_message")),
        {},
    )
    if latest_error:
        st.error(f'{latest_error.get("error_type", "OpenAIError")}: {latest_error.get("error_message", "Request failed.")}')


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
    latest_error = next(
        (item for item in reversed(telemetry.get("steps", [])) if item.get("error_type") or item.get("error_message")),
        {},
    )
    telemetry_bits = [
        ("Model", telemetry.get("model") or "Unavailable"),
        ("Total Tokens", f'{telemetry.get("total_tokens", 0):,}'),
        ("Latency", f'{telemetry.get("latency_ms", 0)} ms'),
        ("Cost", f'${telemetry.get("cost_usd", 0.0):.6f}'),
        ("Latest Step", latest_step),
        ("Status", latest_status.title()),
    ]
    if latest_error:
        telemetry_bits.extend(
            [
                ("OpenAI Error", latest_error.get("error_type", "Unknown")),
                ("Error Attempt", f'{latest_error.get("error_attempt", "?")}/{latest_error.get("error_max_attempts", "?")}'),
            ]
        )
    error_html = ""
    if latest_error:
        error_html = (
            f'<div class="workspace-body-copy">'
            f'{escape_html(latest_error.get("error_message", "OpenAI request failed."))}'
            f"</div>"
        )
    return render_response_card(
        "Observability",
        "Operational telemetry across model usage, workflow state, and execution behavior.",
        f'<div class="observability-grid">{metric_grid_html(telemetry_bits)}</div>{error_html}',
        tone="observability-module",
    )


def render_semantic_profile_card(context: dict | None) -> str:
    if not context:
        return render_response_card(
            "Semantic Profile",
            "Dataset roles inferred for orchestration agents.",
            '<div class="workspace-body-copy">No active semantic profile yet.</div>',
            tone="default-module",
        )

    items = [
        ("Rows", f'{context.get("row_count"):,}' if context.get("row_count") is not None else "Schema"),
        ("Columns", context.get("column_count", 0)),
        ("Metrics", len(context.get("metrics", []))),
        ("Dimensions", len(context.get("dimensions", [])) + len(context.get("categorical_fields", []))),
        ("Time", len(context.get("time_columns", []))),
        ("IDs", len(context.get("identifiers", []))),
    ]
    body = (
        f'<div class="observability-grid">{metric_grid_html(items)}</div>'
        f'<div class="workspace-body-copy">{escape_html(context.get("summary", ""))}</div>'
    )
    return render_response_card(
        "Semantic Profile",
        "Inferred metrics, dimensions, time fields, and identifiers for agent context.",
        body,
        tone="default-module",
    )


def render_analytics_memory_card(memory: dict | None) -> str:
    memory = memory or {}
    previous_chart = memory.get("previous_chart") or {}
    items = [
        ("Turns", len(memory.get("turns", []))),
        ("Dimensions", len(memory.get("previous_dimensions", []))),
        ("Metrics", len(memory.get("previous_metrics", []))),
        ("Filters", len(memory.get("previous_filters", []))),
        ("Chart", previous_chart.get("chart_type") or "Unset"),
        ("Semantic", len(memory.get("semantic_summaries", []))),
    ]
    body = (
        f'<div class="observability-grid">{metric_grid_html(items)}</div>'
        f'<div class="workspace-body-copy">'
        f'{escape_html(memory.get("previous_intent") or "No conversational analytics context captured yet.")}'
        f"</div>"
    )
    return render_response_card(
        "Analytics Memory",
        "Session context available to follow-up planning, SQL generation, insights, and chart recommendations.",
        body,
        tone="default-module",
    )


def render_autonomous_insight_card(insight_state: dict | None) -> str:
    insight_state = insight_state or {}
    findings = insight_state.get("findings", [])
    severity = insight_state.get("severity", "info")
    if findings:
        body = "".join(
            (
                f'<div class="workspace-list-item">'
                f'<div class="observability-label">{escape_html(item.get("severity", "info")).upper()} · {escape_html(item.get("type", "signal"))}</div>'
                f'<div class="workspace-body-copy"><strong>{escape_html(item.get("title", ""))}</strong><br/>{escape_html(item.get("detail", ""))}</div>'
                f"</div>"
            )
            for item in findings[:5]
        )
    else:
        body = '<div class="workspace-body-copy">No autonomous insight scan has run yet.</div>'
    body = (
        f'<div class="observability-grid">{metric_grid_html([("Severity", severity.title()), ("Findings", len(findings))])}</div>'
        f"{body}"
    )
    return render_response_card(
        "Autonomous Insights",
        "Detected trends, anomalies, spikes, drops, outliers, and dominant categories.",
        body,
        tone="insight-module",
    )


def render_investigation_card(investigation_state: dict | None) -> str:
    investigation_state = investigation_state or {}
    queries = investigation_state.get("queries", [])
    status = investigation_state.get("status", "idle")
    telemetry = investigation_state.get("telemetry", {}) or {}
    if queries:
        body = "".join(
            (
                f'<div class="workspace-list-item">'
                f'<div class="observability-label">{escape_html(item.get("status", "pending")).upper()} · {escape_html(item.get("finding_type", "signal"))}</div>'
                f'<div class="workspace-body-copy"><strong>{escape_html(item.get("finding_title", ""))}</strong><br/>'
                f'{escape_html(item.get("summary", ""))}</div>'
                f"</div>"
            )
            for item in queries[:4]
        )
    else:
        body = '<div class="workspace-body-copy">No autonomous drill-down investigation has run yet.</div>'
    metric_items = [
        ("Status", status.title()),
        ("Queries", len(queries)),
        ("Tokens", f'{telemetry.get("total_tokens", 0):,}'),
        ("Cost", f'${telemetry.get("cost_usd", 0.0):.6f}'),
    ]
    body = (
        f'<div class="observability-grid">{metric_grid_html(metric_items)}</div>'
        f'<div class="workspace-body-copy">{escape_html(investigation_state.get("summary", ""))}</div>'
        f"{body}"
    )
    return render_response_card(
        "Drill-Down Investigation",
        "Autonomous follow-up SQL probes for likely root-cause analysis.",
        body,
        tone="insight-module",
    )


def render_monitoring_card(monitoring_state: dict | None, config: dict | None = None) -> str:
    monitoring_state = monitoring_state or {}
    config = config or {}
    checks = monitoring_state.get("checks", [])
    items = [
        ("Status", monitoring_state.get("status", "idle").title()),
        ("Targets", len(config.get("targets", []))),
        ("Checks", len(checks)),
        ("Severity", monitoring_state.get("severity", "info").title()),
        ("Cadence", f'{config.get("interval_minutes", 60)} min'),
        ("Enabled", "Yes" if config.get("enabled") else "No"),
    ]
    check_html = "".join(
        (
            f'<div class="workspace-list-item">'
            f'<div class="observability-label">{escape_html(item.get("severity", "info")).upper()} · {escape_html(item.get("target", ""))}</div>'
            f'<div class="workspace-body-copy">{escape_html((item.get("insight") or {}).get("summary", ""))}</div>'
            f"</div>"
        )
        for item in checks[:5]
    )
    if not check_html:
        check_html = '<div class="workspace-body-copy">No scheduled monitoring run has executed yet.</div>'
    body = (
        f'<div class="observability-grid">{metric_grid_html(items)}</div>'
        f'<div class="workspace-body-copy">{escape_html(monitoring_state.get("summary", ""))}</div>'
        f"{check_html}"
    )
    return render_response_card(
        "Scheduled AI Monitoring",
        "Automated KPI checks for revenue, customers, orders, growth, and anomalies.",
        body,
        tone="observability-module",
    )


def render_executive_briefing_card(briefing_state: dict | None) -> str:
    briefing_state = briefing_state or {}
    sections = briefing_state.get("sections", [])
    items = [
        ("Status", briefing_state.get("status", "idle").title()),
        ("Severity", briefing_state.get("severity", "info").title()),
        ("Sections", len(sections)),
        ("Generated", briefing_state.get("generated_at") or "Pending"),
    ]
    section_html = "".join(
        (
            f'<div class="workspace-list-item">'
            f'<div class="observability-label">{escape_html(item.get("severity", "info")).upper()} · {escape_html(item.get("target", ""))}</div>'
            f'<div class="workspace-body-copy"><strong>{escape_html(item.get("trend", ""))}</strong><br/>'
            f'{escape_html(item.get("investigation", ""))}</div>'
            f"</div>"
        )
        for item in sections[:5]
    )
    if not section_html:
        section_html = '<div class="workspace-body-copy">No executive briefing has been generated yet.</div>'
    body = (
        f'<div class="observability-grid">{metric_grid_html(items)}</div>'
        f'<div class="workspace-body-copy">{escape_html(briefing_state.get("summary", ""))}</div>'
        f"{section_html}"
    )
    return render_response_card(
        "Executive Briefing",
        "KPI status, anomalies, trends, investigations, and severity levels from scheduled monitoring.",
        body,
        tone="summary-module",
    )


def render_workspace_card(identity: dict | None, memory: dict | None) -> str:
    identity = identity or {}
    memory = memory or {}
    items = [
        ("Workspace", identity.get("workspace_id", "default")),
        ("Scope", identity.get("workspace_label", identity.get("workspace_scope", "personal")).title()),
        ("Role", identity.get("role", "viewer").title()),
        ("Queries", len(memory.get("query_history", []))),
        ("Runs", len(memory.get("workflow_runs", []))),
        ("Insights", len(memory.get("generated_insights", []))),
        ("Datasets", len(memory.get("semantic_dataset_memory", {}))),
    ]
    body = (
        f'<div class="observability-grid">{metric_grid_html(items)}</div>'
        f'<div class="workspace-body-copy">Team {escape_html(identity.get("team_id", "default-team"))} '
        f'is active for {escape_html(identity.get("display_name", identity.get("user_id", "user")))}. '
        f'Workspace scope is {escape_html(identity.get("workspace_scope", "personal"))}; shared assets retain owner and visibility metadata.</div>'
    )
    return render_response_card(
        "Enterprise Workspace",
        "Authentication-ready user, team, RBAC, and persistent workspace memory.",
        body,
        tone="default-module",
    )


def render_executive_summary(question: str, df: pd.DataFrame, exec_time: float | None, telemetry: dict) -> str:
    shape_text = f"{len(df):,} rows x {len(df.columns)} columns"
    lead_column = df.columns[0] if not df.empty else "N/A"
    exec_time_text = f"{exec_time:.2f}s" if exec_time is not None else "pending runtime"

    total_tokens = telemetry.get("total_tokens", 0)
    formatted_tokens = f"{total_tokens:,}"

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
        f"{escape_html(formatted_tokens)} tokens processed. "
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
