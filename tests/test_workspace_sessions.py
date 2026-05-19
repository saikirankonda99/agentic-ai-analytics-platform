from __future__ import annotations

from workspace import append_session_transcript, bookmark_investigation, default_workspace_memory, start_workspace_session


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
