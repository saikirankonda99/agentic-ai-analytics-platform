from __future__ import annotations

import pandas as pd
import streamlit as st

from ui.dashboard import (
    escape_html,
    render_investigation_card,
    render_recommendation_card,
    render_response_card,
    render_saved_assets_card,
    render_semantic_profile_card,
    render_workspace_card,
    render_workflow_timeline_cards,
)
from ui.views.common import ViewServices
from ui.views.orchestration import render_session_replay_card
from ui.views.telemetry import render_platform_summary


def render_investigations_workspace(services: ViewServices) -> None:
    render_platform_summary()
    identity = st.session_state.get("user_identity")
    memory = st.session_state.get("workspace_memory", {})
    current = st.session_state.get("investigation_state")
    stored = memory.get("investigations", [])
    left, right = st.columns([1.15, 0.85], gap="medium")
    with left:
        st.markdown(render_investigation_card(current), unsafe_allow_html=True)
        bookmark_col, pin_col = st.columns(2, gap="small")
        with bookmark_col:
            if st.button("Bookmark Investigation", width="stretch"):
                services.persist_investigation_bookmark()
                st.success("Investigation bookmarked for this workspace session.")
        with pin_col:
            if st.button("Pin Investigation", width="stretch"):
                services.persist_investigation_pin()
                st.success("Investigation pinned for follow-up.")
        if st.button("Share Investigation", width="stretch"):
            if services.persist_shared_investigation():
                st.success("Investigation shared when available.")
        st.markdown(render_workflow_timeline_cards(st.session_state.live_trace or st.session_state.workflow_trace), unsafe_allow_html=True)
    with right:
        st.markdown(
            render_response_card(
                "Investigation Sessions",
                "Persisted autonomous drill-down sessions for this workspace.",
                "".join(
                    f'<div class="workspace-list-item"><div class="observability-label">{escape_html(item.get("run_id", item.get("saved_id", "run")))} · {escape_html("Shared" if item.get("visibility") == "team" else "Private")}</div>'
                    f'<div class="workspace-body-copy">Owner: {escape_html(item.get("owner_name", item.get("owner_id", "Unknown")))}<br/>{escape_html(item.get("summary", ""))}</div></div>'
                    for item in reversed(stored[-6:])
                )
                or '<div class="workspace-body-copy">No persisted investigation sessions yet.</div>',
                tone="insight-module",
            ),
            unsafe_allow_html=True,
        )
        st.markdown(render_workspace_card(identity, memory), unsafe_allow_html=True)
        st.markdown(render_saved_assets_card(memory), unsafe_allow_html=True)
        st.markdown(render_semantic_profile_card(st.session_state.get("semantic_context")), unsafe_allow_html=True)
        st.markdown(render_session_replay_card(memory), unsafe_allow_html=True)
        recommendation_df = st.session_state.latest_df if st.session_state.latest_df is not None else pd.DataFrame()
        st.markdown(
            render_recommendation_card(
                services.build_ai_recommendations(
                    recommendation_df,
                    st.session_state.workflow_telemetry,
                    st.session_state.workflow_trace,
                )
            ),
            unsafe_allow_html=True,
        )
