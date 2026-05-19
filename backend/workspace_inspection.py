from __future__ import annotations

from typing import Any


def workspace_summary(memory: dict[str, Any] | None) -> dict[str, Any]:
    memory = memory or {}
    sessions = list(memory.get("sessions", []))
    telemetry = list(memory.get("telemetry_summaries", []))
    failed = [item for item in telemetry if item.get("error_type")]
    total_latency = sum(float(item.get("latency_ms", 0) or 0) for item in telemetry)
    total_tokens = sum(int(item.get("total_tokens", 0) or 0) for item in telemetry)
    total_cost = sum(float(item.get("cost_usd", 0.0) or 0.0) for item in telemetry)
    active_session = next((item for item in reversed(sessions) if item.get("status") == "active"), None)
    return {
        "workspace_id": memory.get("workspace_id", "unknown"),
        "team_id": memory.get("team_id", "unknown"),
        "member_count": len(memory.get("members", {})),
        "query_count": len(memory.get("query_history", [])),
        "workflow_count": len(memory.get("workflow_runs", [])),
        "investigation_count": len(memory.get("investigations", [])),
        "bookmark_count": len(memory.get("bookmarks", [])),
        "session_count": len(sessions),
        "active_session_id": (active_session or {}).get("session_id"),
        "transcript_count": sum(len(item.get("transcripts", [])) for item in sessions),
        "semantic_memory_categories": {
            "schema_memory": len(memory.get("semantic_dataset_memory", {})),
            "workflow_memory": len(memory.get("workflow_runs", [])),
            "investigation_memory": len(memory.get("investigations", [])),
            "telemetry_memory": len(memory.get("telemetry_summaries", [])),
        },
        "telemetry": {
            "run_count": len(telemetry),
            "error_rate": round((len(failed) / len(telemetry)) * 100, 2) if telemetry else 0.0,
            "avg_latency_ms": round(total_latency / len(telemetry), 2) if telemetry else 0.0,
            "total_tokens": total_tokens,
            "estimated_cost_usd": round(total_cost, 6),
        },
        "updated_at": memory.get("updated_at"),
    }


def workflow_transcripts(memory: dict[str, Any] | None, session_id: str | None = None) -> list[dict[str, Any]]:
    memory = memory or {}
    transcripts: list[dict[str, Any]] = []
    for session in memory.get("sessions", []):
        if session_id and session.get("session_id") != session_id:
            continue
        for transcript in session.get("transcripts", []):
            transcripts.append(
                {
                    "session_id": session.get("session_id"),
                    "session_label": session.get("label"),
                    **transcript,
                }
            )
    return transcripts


def saved_sql_history(memory: dict[str, Any] | None, limit: int = 25) -> list[dict[str, Any]]:
    memory = memory or {}
    rows = []
    for item in reversed(memory.get("query_history", [])[-limit:]):
        rows.append(
            {
                "run_id": item.get("run_id"),
                "timestamp": item.get("timestamp"),
                "question": item.get("question"),
                "intent": item.get("intent"),
                "sql": item.get("sql"),
                "rows": item.get("rows", 0),
            }
        )
    return rows


__all__ = ["saved_sql_history", "workflow_transcripts", "workspace_summary"]
