"""The small-business entry flow, separate from the operator workspace."""
from __future__ import annotations

from html import escape

import streamlit as st

from csv_analytics import DEMO_PATH, SUPPORTED_QUESTIONS


def _open_sales() -> None:
    st.session_state.top_navigation = "Overview"
    st.session_state.workspace_route = "Overview"


def render_customer_sidebar() -> dict:
    identity = st.session_state.get("auth_session") or {}
    with st.sidebar.expander("Workspace settings", expanded=False):
        scope = st.radio(
            "Workspace scope", ["Personal", "Shared team"],
            index=1 if identity.get("workspace_scope") == "team" else 0,
            horizontal=True, key="workspace_scope_choice",
        )
        clear = st.button("Clear session", width="stretch")
    config = st.session_state.get("monitoring_config", {})
    return {
        "nav": "Overview", "clear_chat": clear, "show_schema": False,
        "workspace_scope": scope, "workspace_user": identity.get("user_id", ""),
        "workspace_team": identity.get("team_id", ""),
        "workspace_role": identity.get("role", "viewer"),
        "monitoring_enabled": config.get("enabled", False),
        "monitoring_targets": config.get("targets", []),
        "monitoring_interval": config.get("interval_minutes", 60),
        "run_monitoring": False,
    }


def render_step_progress(stage: int) -> None:
    labels = ["Upload & review", "Ask a question", "Answer & download"]
    parts = []
    for number, label in enumerate(labels, 1):
        state = "is-current" if number == stage else "is-complete" if number < stage else ""
        current = ' aria-current="step"' if number == stage else ""
        parts.append(
            f'<li class="customer-step {state}"{current}>'
            f'<span class="step-number">{number}</span><span>{escape(label)}</span></li>'
        )
    st.markdown(
        '<ol class="customer-steps" aria-label="Your sales review">' + "".join(parts) + "</ol>",
        unsafe_allow_html=True,
    )


def render_customer_data_controls(sidebar_state: dict) -> dict:
    ready = "uploaded_df" in st.session_state
    title = "Your sales data · Change file" if ready else "1 · Upload your sales file"
    with st.expander(title, expanded=not ready):
        if not ready:
            st.markdown("Start with a CSV export from your sales system.")
        st.caption("CSV only · Up to 10 MB and 50,000 rows · Review your columns before analysis.")
        identity = st.session_state.get("auth_session") or {}
        scope = sidebar_state["workspace_scope"]
        uploaded_file = st.file_uploader(
            "Upload your sales CSV", type=["csv"], max_upload_size=10,
            key=f"sales_upload_{identity.get('team_id', '')}_{identity.get('user_id', '')}_{scope}_{st.session_state.get('upload_generation', 0)}",
            on_change=_open_sales,
        )
        left, right = st.columns(2)
        load_demo = left.button("Try sample data", width="stretch", on_click=_open_sales)
        right.download_button(
            "Download sample CSV", DEMO_PATH.read_bytes(), "retail-sales.csv", "text/csv", width="stretch",
        )
        st.caption("Sample data is fictional. For an Excel file, export the sheet as CSV first.")
    return {"uploaded_file": uploaded_file, "load_demo": load_demo, "use_database": False}


def _set_question(question: str) -> None:
    st.session_state.command_input = question
    st.session_state.command_text = question


def render_customer_question() -> str | None:
    st.markdown("### Ask your business question")
    st.caption("Start with sales totals, products, months, or countries. Each calculation uses all accepted rows.")
    with st.form("customer_question_form", clear_on_submit=False):
        question_col, action_col = st.columns([5, 1.3], vertical_alignment="bottom")
        question = question_col.text_input(
            "Your business question", key="command_input",
            placeholder="Which products generated the most revenue?", label_visibility="collapsed",
        )
        submitted = action_col.form_submit_button("Get answer", type="primary", width="stretch")
    prompt = None
    available = st.session_state.get("csv_import_available_questions", SUPPORTED_QUESTIONS)
    actions = [
        ("Total Revenue", "Total revenue", ()),
        ("Revenue by Product", "Revenue by product", ("product",)),
        ("Monthly Revenue", "Revenue by month", ("date",)),
        ("Sales Summary", "Sales summary", ()),
        ("Revenue by Country", "Revenue by country", ("country",)),
        ("Units Sold by Product", "Units sold by product", ("product", "quantity")),
    ]
    with st.expander("Common questions", expanded=False):
        for offset in range(0, len(actions), 3):
            for column, (label, action, required) in zip(st.columns(3), actions[offset:offset + 3]):
                disabled = action not in available
                missing = [name for name in required if name not in st.session_state.uploaded_df.columns]
                help_text = (
                    "Upload your file again and map " + ", ".join(missing or required) + " during review."
                    if disabled else "Calculate this answer from all accepted sales rows."
                )
                if column.button(
                    label, width="stretch", disabled=disabled, help=help_text,
                    on_click=_set_question, args=(action,),
                ):
                    prompt = action
        unavailable = [label for label, action, _ in actions if action not in available]
        if unavailable:
            st.caption("Some questions need additional columns: " + ", ".join(unavailable) + ".")
    if submitted and question.strip():
        st.session_state.command_text = question.strip()
        return question.strip()
    return prompt


def render_customer_downloads() -> None:
    frame = st.session_state.get("latest_df")
    if frame is None:
        return
    analysis = st.session_state.get("latest_csv_analysis") or {}
    ai = st.session_state.get("customer_ai_explanation") or {}
    sections = [
        "# Sales review",
        "Question: " + st.session_state.get("latest_question", ""),
        "Data: " + (st.session_state.get("uploaded_name") or "Sales CSV"),
        f"Source rows: {analysis.get('source_rows', len(frame))}",
        "## Calculated answer\n" + st.session_state.get("latest_insight", ""),
    ]
    if ai.get("text"):
        sections.append("## AI assistance\n" + ai["text"])
    if analysis.get("warnings"):
        sections.append("## Data notes\n" + "\n".join(analysis["warnings"]))
    sections.append("Figures describe the uploaded records. They do not establish causes, profit, or future sales.")
    left, right = st.columns(2)
    left.download_button(
        "Download results CSV", frame.to_csv(index=False).encode("utf-8"),
        "sales-results.csv", "text/csv", width="stretch",
    )
    right.download_button(
        "Download summary", "\n\n".join(sections).encode("utf-8"),
        "sales-summary.md", "text/markdown", width="stretch",
    )
