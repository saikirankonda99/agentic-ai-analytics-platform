from __future__ import annotations

from investigation import empty_investigation_state, investigation_lifecycle_event, score_investigation


def test_investigation_lifecycle_event_shape() -> None:
    event = investigation_lifecycle_event("planning", "completed", "ok")

    assert event["stage"] == "planning"
    assert event["status"] == "completed"
    assert event["timestamp"]


def test_investigation_score_uses_evidence_and_success() -> None:
    state = {
        **empty_investigation_state(),
        "severity": "warning",
        "queries": [{"status": "success"}, {"status": "error"}],
        "evidence": [{"summary": "evidence"}],
    }

    assert score_investigation(state) > 0
