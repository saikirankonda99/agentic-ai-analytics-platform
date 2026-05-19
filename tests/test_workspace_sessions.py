from __future__ import annotations

from workspace import (
    append_session_transcript,
    bookmark_investigation,
    bookmark_query,
    default_workspace_memory,
    onboarding_progress,
    pin_investigation,
    save_report_view,
    save_workspace_preferences,
    start_workspace_session,
    update_onboarding_step,
)


def test_workspace_session_transcript_persistence() -> None:
    memory = default_workspace_memory()
    session = start_workspace_session(memory, label="Test session")
    append_session_transcript(
        memory,
        session_id=session["session_id"],
        transcript={"workflow_id": "wf-test", "question": "List customers"},
    )

    stored = memory["sessions"][-1]
    assert stored["session_id"] == session["session_id"]
    assert stored["workflow_ids"] == ["wf-test"]
    assert stored["transcripts"][0]["question"] == "List customers"


def test_bookmark_investigation_skips_idle_and_persists_completed() -> None:
    memory = default_workspace_memory()
    bookmark_investigation(memory, {"status": "idle"})
    assert memory["bookmarks"] == []

    bookmark_investigation(memory, {"status": "completed", "summary": "Found anomaly", "queries": []}, note="Review")
    assert memory["bookmarks"][0]["summary"] == "Found anomaly"
    assert memory["bookmarks"][0]["note"] == "Review"


def test_onboarding_progress_tracks_completed_steps() -> None:
    memory = default_workspace_memory()

    update_onboarding_step(memory, "workspace_intro")
    update_onboarding_step(memory, "sample_dataset")
    progress = onboarding_progress(memory)

    assert progress["completed_count"] == 2
    assert progress["total_count"] >= 5
    assert progress["steps"]["workspace_intro"] is True
    assert memory["recent_activity"][-1]["activity_type"] == "onboarding_updated"


def test_workspace_preferences_reports_query_bookmarks_and_pins_persist() -> None:
    memory = default_workspace_memory()

    save_workspace_preferences(memory, {"default_route": "Operations", "compact_results": True})
    bookmark_query(memory, {"question": "Revenue", "sql": "select 1", "rows": 1}, note="Reusable")
    pin_investigation(memory, {"status": "completed", "summary": "Revenue drop", "queries": []}, note="Exec review")
    save_report_view(memory, {"title": "Weekly summary", "scope": "operations", "summary": "Healthy"})

    assert memory["workspace_preferences"]["default_route"] == "Operations"
    assert memory["query_bookmarks"][0]["note"] == "Reusable"
    assert memory["pinned_investigations"][0]["summary"] == "Revenue drop"
    assert memory["saved_reports"][0]["title"] == "Weekly summary"
