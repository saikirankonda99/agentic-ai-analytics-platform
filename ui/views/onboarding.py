from __future__ import annotations

import streamlit as st

from ui.dashboard import escape_html, render_onboarding_card, render_quick_actions_card, render_response_card
from ui.views.common import ViewServices
from workspace import ONBOARDING_STEPS, dismiss_onboarding, onboarding_progress, update_onboarding_step


def render_onboarding_workspace_panel(services: ViewServices) -> None:
    memory = st.session_state.get("workspace_memory", {})
    progress = onboarding_progress(memory)
    preferences = memory.get("workspace_preferences", {})
    if progress.get("dismissed") or not preferences.get("show_onboarding", True):
        return
    st.markdown(render_onboarding_card(progress, ONBOARDING_STEPS), unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4, gap="small")
    if c1.button("Use sample dataset", help="Keeps the bundled Chinook SQL dataset active.", width="stretch"):
        memory = update_onboarding_step(st.session_state.get("workspace_memory", {}), "sample_dataset")
        st.session_state.workspace_memory = memory
        services.persist_workspace_memory()
        st.success("Sample dataset is ready.")
    if c2.button("Try guided query", help="Loads a good first question into the command workspace.", width="stretch"):
        st.session_state.command_text = "Revenue by country"
        memory = update_onboarding_step(st.session_state.get("workspace_memory", {}), "first_query")
        st.session_state.workspace_memory = memory
        services.persist_workspace_memory()
        st.rerun()
    if c3.button("Save preferences", help="Restores this workspace route and chart type next time.", width="stretch"):
        services.persist_workspace_preferences(
            last_route=st.session_state.get("workspace_route", "Overview"),
            preferred_chart_type=st.session_state.get("chart_type", "Bar"),
        )
        st.success("Workspace preferences saved.")
    if c4.button("Hide guide", help="Hide the onboarding guide for this workspace.", width="stretch"):
        memory = dismiss_onboarding(st.session_state.get("workspace_memory", {}))
        st.session_state.workspace_memory = memory
        services.persist_workspace_memory()
        st.rerun()


def render_quick_actions_panel() -> None:
    memory = st.session_state.get("workspace_memory", {})
    recent = list(reversed(memory.get("recent_activity", [])[-3:]))
    quick_actions = [
        {"label": "Run a guided query", "caption": "Use Revenue by Country, Top Customers, or Top Tracks to populate the workspace."},
        {"label": "Review saved work", "caption": f'{len(memory.get("query_bookmarks", []))} query bookmarks and {len(memory.get("saved_reports", []))} reports available.'},
        {"label": "Export current context", "caption": "Download CSV, executive summary, telemetry, or trace from the active workflow."},
        {"label": "Recover workflow", "caption": "Check recovery guidance when validation, connector, or OpenAI calls fail."},
    ]
    st.markdown(render_quick_actions_card(quick_actions), unsafe_allow_html=True)
    if recent:
        st.markdown(
            render_response_card(
                "Recent Shortcuts",
                "Fast return paths from your latest workspace activity.",
                "".join(
                    f'<div class="workspace-list-item"><div class="observability-label">{escape_html(item.get("activity_type", ""))}</div>'
                    f'<div class="workspace-body-copy">{escape_html(item.get("title", ""))}<br/>{escape_html(item.get("detail", ""))}</div></div>'
                    for item in recent
                ),
                tone="default-module",
            ),
            unsafe_allow_html=True,
        )
