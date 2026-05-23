from __future__ import annotations

from workspace import (
    as_team_workspace,
    append_session_transcript,
    bookmark_investigation,
    bookmark_query,
    build_user_session,
    can_edit_resource,
    default_workspace_memory,
    onboarding_progress,
    pin_investigation,
    record_collaboration_event,
    save_report_view,
    save_investigation_record,
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


def test_shared_report_persistence_records_owner_and_activity() -> None:
    identity = build_user_session("analyst.one", "growth", "analyst", display_name="Analyst One")
    memory = default_workspace_memory(as_team_workspace(identity))

    save_report_view(
        memory,
        {"title": "Team revenue view", "scope": "analytics", "summary": "Revenue healthy"},
        identity=identity,
        visibility="team",
    )

    report = memory["saved_reports"][0]
    assert report["visibility"] == "team"
    assert report["owner_id"] == "analyst.one"
    assert report["created_by_name"] == "Analyst One"
    assert report["updated_at"]
    assert memory["collaboration_events"][0]["event_type"] == "report_shared"


def test_shared_investigation_visibility_and_collaboration_history() -> None:
    identity = build_user_session("analyst.two", "growth", "analyst", display_name="Analyst Two")
    memory = default_workspace_memory(as_team_workspace(identity))

    save_investigation_record(
        memory,
        {"status": "completed", "summary": "Margin anomaly", "queries": []},
        note="Review together",
        identity=identity,
        visibility="team",
    )

    assert memory["investigations"][0]["visibility"] == "team"
    assert memory["investigations"][0]["owner_name"] == "Analyst Two"
    assert memory["collaboration_events"][0]["resource_type"] == "investigation"


def test_workspace_switching_and_owner_validation() -> None:
    identity = build_user_session("owner.user", "growth", "analyst")
    team_identity = as_team_workspace(identity)

    assert identity["workspace_id"] == "growth.owner.user"
    assert team_identity["workspace_id"] == "growth.shared"
    assert team_identity["workspace_scope"] == "team"

    resource = {"owner_id": "owner.user"}
    viewer = build_user_session("viewer.user", "growth", "viewer")
    admin = build_user_session("admin.user", "growth", "admin")

    assert can_edit_resource(identity, resource) is True
    assert can_edit_resource(viewer, resource) is False
    assert can_edit_resource(admin, resource) is True


def test_collaboration_event_persistence_shape() -> None:
    identity = build_user_session("analyst.three", "growth", "analyst")
    memory = default_workspace_memory(as_team_workspace(identity))

    record_collaboration_event(
        memory,
        event_type="dashboard_shared",
        resource_type="dashboard_view",
        resource_id="dashboard-1",
        title="Dashboard view shared",
        actor=identity,
    )

    assert memory["collaboration_events"][0]["resource_id"] == "dashboard-1"
    assert memory["recent_activity"][-1]["activity_type"] == "dashboard_shared"
