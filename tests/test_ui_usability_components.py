from __future__ import annotations

from ui.dashboard import (
    render_empty_state_card,
    render_onboarding_card,
    render_quick_actions_card,
    render_recovery_guidance_card,
    render_saved_assets_card,
)
from workspace import ONBOARDING_STEPS, default_workspace_memory, onboarding_progress, update_onboarding_step


def test_onboarding_card_renders_progress_and_steps() -> None:
    memory = default_workspace_memory()
    update_onboarding_step(memory, "workspace_intro")

    html = render_onboarding_card(onboarding_progress(memory), ONBOARDING_STEPS)

    assert "Workspace Onboarding" in html
    assert "1 of 5 onboarding steps complete" in html
    assert "Workspace introduced" in html


def test_usability_cards_escape_and_render_operational_content() -> None:
    memory = default_workspace_memory()
    memory["query_bookmarks"].append({"sql": "select 1"})
    recovery_html = render_recovery_guidance_card(
        {"steps": [{"error_type": "RateLimitError", "error_message": "Too many requests <retry>"}]},
        {"warnings": ["SELECT-only validation warning"]},
        {"message": "Retry with a narrower date range."},
    )

    assert "Workspace Continuity" in render_saved_assets_card(memory)
    assert "Quick Actions" in render_quick_actions_card([{"label": "Export", "caption": "Download report"}])
    assert "No rows" in render_empty_state_card("No rows", "Empty", ["Try again"])
    assert "&lt;retry&gt;" in recovery_html
    assert "SELECT-only validation warning" in recovery_html
