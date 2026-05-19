from __future__ import annotations

from backend.workspace_inspection import saved_sql_history, workflow_transcripts, workspace_summary


def test_workspace_summary_rolls_up_sessions_and_telemetry() -> None:
    memory = {
        "workspace_id": "team.user",
        "team_id": "team",
        "members": {"user": {"role": "admin"}},
        "query_history": [{"sql": "select 1"}],
        "workflow_runs": [{"run_id": "run-1"}],
        "investigations": [{"status": "completed"}],
        "bookmarks": [{"bookmark_id": "bookmark-1"}],
        "semantic_dataset_memory": {"albums": {}},
        "telemetry_summaries": [
            {"latency_ms": 100, "total_tokens": 10, "cost_usd": 0.01},
            {"latency_ms": 300, "total_tokens": 20, "cost_usd": 0.02, "error_type": "RuntimeError"},
        ],
        "sessions": [
            {
                "session_id": "session-1",
                "status": "active",
                "transcripts": [{"run_id": "run-1", "question": "show sales"}],
            }
        ],
    }

    summary = workspace_summary(memory)

    assert summary["workspace_id"] == "team.user"
    assert summary["session_count"] == 1
    assert summary["transcript_count"] == 1
    assert summary["telemetry"]["error_rate"] == 50.0
    assert summary["telemetry"]["avg_latency_ms"] == 200.0


def test_workspace_transcript_and_sql_exports() -> None:
    memory = {
        "query_history": [{"run_id": "run-1", "sql": "select 1", "question": "q"}],
        "sessions": [
            {"session_id": "session-1", "label": "Ops", "transcripts": [{"run_id": "run-1"}]},
            {"session_id": "session-2", "label": "Ops", "transcripts": [{"run_id": "run-2"}]},
        ],
    }

    assert len(workflow_transcripts(memory, session_id="session-1")) == 1
    assert saved_sql_history(memory)[0]["sql"] == "select 1"
