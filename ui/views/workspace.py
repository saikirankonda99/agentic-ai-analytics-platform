from __future__ import annotations

import time

import streamlit as st

from backend.workspace_inspection import saved_sql_history
from ui.dashboard import escape_html, render_history, render_response_card, render_saved_assets_card
from ui.views.common import ViewServices, latest_items, record_render_timing
from ui.views.reports import render_report_exports


def _resource_meta(item: dict) -> str:
    visibility = "Shared" if item.get("visibility") == "team" else "Private"
    owner = item.get("owner_name") or item.get("created_by_name") or item.get("owner_id") or "Unknown owner"
    updated = item.get("updated_at") or item.get("created_at") or item.get("saved_at") or item.get("timestamp") or ""
    return f"{visibility} · Owner: {owner} · Updated: {updated}"


def render_workspace_history(services: ViewServices) -> None:
    started_at = time.perf_counter()
    memory = st.session_state.get("workspace_memory", {})
    render_history(st.session_state.history)
    st.markdown(render_saved_assets_card(memory), unsafe_allow_html=True)
    left, right = st.columns([1, 1], gap="medium")
    with left:
        saved_queries = saved_sql_history(memory, limit=8)
        st.markdown(
            render_response_card(
                "Saved Query History",
                "User-scoped SQL history restored from persistent workspace memory.",
                "".join(
                    f'<div class="workspace-list-item"><div class="observability-label">{escape_html(item.get("timestamp", ""))}</div>'
                    f'<div class="workspace-body-copy">{escape_html(item.get("question", ""))}<br/><code>{escape_html(item.get("sql", ""))}</code></div></div>'
                    for item in saved_queries
                )
                or '<div class="workspace-body-copy">No saved SQL history for this workspace.</div>',
                tone="summary-module",
            ),
            unsafe_allow_html=True,
        )
    with right:
        recent_activity = latest_items(memory.get("recent_activity", []), 8)
        collab_events = latest_items(memory.get("collaboration_events", []), 6)
        st.markdown(
            render_response_card(
                "Recent Activity",
                "Workspace restoration, shared actions, saved investigations, saved SQL, exports, and workflow persistence events.",
                "".join(
                    f'<div class="workspace-list-item"><div class="observability-label">{escape_html(item.get("activity_type", ""))} · {escape_html(item.get("timestamp", ""))}</div>'
                    f'<div class="workspace-body-copy">{escape_html(item.get("title", ""))}<br/>{escape_html(item.get("detail", ""))}<br/>Actor: {escape_html(item.get("actor_name") or item.get("actor_id") or "System")}</div></div>'
                    for item in recent_activity
                )
                or '<div class="workspace-body-copy">No recent workspace activity yet.</div>',
                tone="default-module",
            ),
            unsafe_allow_html=True,
        )
        st.markdown(
            render_response_card(
                "Recent Collaboration",
                "Team-visible report, bookmark, investigation, and dashboard sharing events.",
                "".join(
                    f'<div class="workspace-list-item"><div class="observability-label">{escape_html(item.get("event_type", ""))} · {escape_html(item.get("timestamp", ""))}</div>'
                    f'<div class="workspace-body-copy">{escape_html(item.get("title", ""))}<br/>{escape_html(item.get("detail", ""))}<br/>By {escape_html(item.get("actor_name") or item.get("actor_id") or "Unknown")}</div></div>'
                    for item in collab_events
                )
                or '<div class="workspace-body-copy">No shared workspace activity yet.</div>',
                tone="observability-module",
            ),
            unsafe_allow_html=True,
        )
    lower_left, lower_right = st.columns([1, 1], gap="medium")
    with lower_left:
        bookmarks = latest_items(memory.get("query_bookmarks", []), 8)
        st.markdown(
            render_response_card(
                "Bookmarked Queries",
                "Reusable SQL workflows saved for repeat analysis.",
                "".join(
                    f'<div class="workspace-list-item"><div class="observability-label">{escape_html(item.get("created_at", ""))}</div>'
                    f'<div class="workspace-body-copy">{escape_html(_resource_meta(item))}<br/>{escape_html(item.get("question", ""))}<br/><code>{escape_html(item.get("sql", ""))}</code></div></div>'
                    for item in bookmarks
                )
                or '<div class="workspace-body-copy">No query bookmarks yet.</div>',
                tone="recommendation-module",
            ),
            unsafe_allow_html=True,
        )
    with lower_right:
        reports = latest_items(memory.get("saved_reports", []), 8)
        st.markdown(
            render_response_card(
                "Saved Report Views",
                "Executive summaries and report snapshots retained for workspace continuity.",
                "".join(
                    f'<div class="workspace-list-item"><div class="observability-label">{escape_html(item.get("scope", ""))} · {escape_html(item.get("created_at", ""))}</div>'
                    f'<div class="workspace-body-copy">{escape_html(_resource_meta(item))}<br/>{escape_html(item.get("title", ""))}<br/>{escape_html(item.get("summary", ""))}</div></div>'
                    for item in reports
                )
                or '<div class="workspace-body-copy">No saved report views yet.</div>',
                tone="summary-module",
            ),
            unsafe_allow_html=True,
        )
    render_timings = latest_items(st.session_state.get("_render_timings", []), 6)
    persistence_timings = latest_items(st.session_state.get("workspace_persistence_timings", []), 6)
    st.markdown(
        render_response_card(
            "Performance Diagnostics",
            "Recent render and persistence timings for the local workspace session.",
            "".join(
                f'<div class="workspace-list-item"><div class="observability-label">Render · {escape_html(item.get("section", ""))}</div>'
                f'<div class="workspace-body-copy">{escape_html(item.get("elapsed_ms", 0))} ms</div></div>'
                for item in render_timings
            )
            + "".join(
                f'<div class="workspace-list-item"><div class="observability-label">Persistence · {escape_html(item.get("operation", ""))}</div>'
                f'<div class="workspace-body-copy">{escape_html(item.get("elapsed_ms", 0))} ms · {escape_html(item.get("workspace_id", ""))}</div></div>'
                for item in persistence_timings
            )
            or '<div class="workspace-body-copy">Performance timings will appear after workspace navigation, exports, or persistence actions.</div>',
            tone="observability-module",
        ),
        unsafe_allow_html=True,
    )
    render_report_exports(services, scope="workspace")
    record_render_timing("workspace_history", started_at)
