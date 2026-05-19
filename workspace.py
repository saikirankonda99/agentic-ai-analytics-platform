from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4


BASE_DIR = Path(__file__).resolve().parent
WORKSPACE_DIR = BASE_DIR / "data" / "workspaces"

ROLE_CAPABILITIES = {
    "admin": ["query", "monitor", "investigate", "brief", "manage_workspace"],
    "analyst": ["query", "monitor", "investigate", "brief"],
    "viewer": ["query", "brief"],
}


def default_user_session() -> dict[str, Any]:
    return {
        "user_id": "local.user",
        "display_name": "Local Analyst",
        "team_id": "default-team",
        "workspace_id": "default-team.local.user",
        "role": "admin",
        "auth_provider": "local-dev",
        "authenticated": True,
    }


def default_workspace_memory(identity: dict[str, Any] | None = None) -> dict[str, Any]:
    identity = identity or default_user_session()
    return {
        "workspace_id": identity.get("workspace_id", "default-team.local.user"),
        "team_id": identity.get("team_id", "default-team"),
        "members": {
            identity.get("user_id", "local.user"): {
                "display_name": identity.get("display_name", "Local Analyst"),
                "role": identity.get("role", "admin"),
            }
        },
        "query_history": [],
        "workflow_runs": [],
        "investigations": [],
        "generated_insights": [],
        "telemetry_summaries": [],
        "semantic_dataset_memory": {},
        "sessions": [],
        "bookmarks": [],
        "updated_at": None,
    }


def _safe_id(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9_.-]+", "-", value.strip())
    return value.strip("-") or "default"


def workspace_id(team_id: str, user_id: str) -> str:
    return f"{_safe_id(team_id)}.{_safe_id(user_id)}"


def build_user_session(user_id: str, team_id: str, role: str, display_name: str | None = None) -> dict[str, Any]:
    safe_role = role if role in ROLE_CAPABILITIES else "viewer"
    return {
        "user_id": _safe_id(user_id or "local.user"),
        "display_name": display_name or user_id or "Local Analyst",
        "team_id": _safe_id(team_id or "default-team"),
        "workspace_id": workspace_id(team_id or "default-team", user_id or "local.user"),
        "role": safe_role,
        "auth_provider": "session-local",
        "authenticated": True,
    }


def user_can(identity: dict[str, Any] | None, capability: str) -> bool:
    role = (identity or {}).get("role", "viewer")
    return capability in ROLE_CAPABILITIES.get(role, [])


def _workspace_path(workspace_key: str) -> Path:
    WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
    return WORKSPACE_DIR / f"{_safe_id(workspace_key)}.json"


def load_workspace_memory(identity: dict[str, Any]) -> dict[str, Any]:
    path = _workspace_path(identity["workspace_id"])
    if not path.exists():
        return default_workspace_memory(identity)
    try:
        stored = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        stored = {}
    memory = default_workspace_memory(identity)
    memory.update(stored)
    memory.setdefault("members", {}).setdefault(
        identity["user_id"],
        {"display_name": identity.get("display_name", identity["user_id"]), "role": identity.get("role", "viewer")},
    )
    return memory


def load_workspace_memory_by_id(workspace_key: str) -> dict[str, Any]:
    identity = default_user_session()
    identity["workspace_id"] = _safe_id(workspace_key)
    return load_workspace_memory(identity)


def save_workspace_memory(identity: dict[str, Any], memory: dict[str, Any]) -> dict[str, Any]:
    memory = dict(memory or default_workspace_memory(identity))
    memory["workspace_id"] = identity["workspace_id"]
    memory["team_id"] = identity["team_id"]
    memory["updated_at"] = datetime.now().isoformat(timespec="seconds")
    memory.setdefault("members", {})[identity["user_id"]] = {
        "display_name": identity.get("display_name", identity["user_id"]),
        "role": identity.get("role", "viewer"),
    }
    _workspace_path(identity["workspace_id"]).write_text(json.dumps(memory, indent=2), encoding="utf-8")
    return memory


def _append_limited(memory: dict[str, Any], key: str, item: dict[str, Any], limit: int = 50) -> None:
    values = list(memory.get(key, []))
    values.append(item)
    memory[key] = values[-limit:]


def start_workspace_session(memory: dict[str, Any], label: str | None = None) -> dict[str, Any]:
    sessions = list(memory.get("sessions", []))
    active = next((item for item in reversed(sessions) if item.get("status") == "active"), None)
    if active:
        return active
    session = {
        "session_id": f"session-{uuid4().hex[:10]}",
        "label": label or "Analytics operations session",
        "status": "active",
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "workflow_ids": [],
        "transcripts": [],
    }
    _append_limited(memory, "sessions", session, limit=20)
    return session


def append_session_transcript(
    memory: dict[str, Any],
    *,
    session_id: str,
    transcript: dict[str, Any],
) -> dict[str, Any]:
    sessions = list(memory.get("sessions", []))
    for item in sessions:
        if item.get("session_id") == session_id:
            item.setdefault("transcripts", []).append(transcript)
            item["transcripts"] = item["transcripts"][-25:]
            if transcript.get("workflow_id"):
                item.setdefault("workflow_ids", []).append(transcript["workflow_id"])
                item["workflow_ids"] = list(dict.fromkeys(item["workflow_ids"]))[-25:]
            item["updated_at"] = datetime.now().isoformat(timespec="seconds")
            break
    memory["sessions"] = sessions
    return memory


def bookmark_investigation(memory: dict[str, Any], investigation: dict[str, Any], note: str = "") -> dict[str, Any]:
    if not investigation or investigation.get("status") in {None, "idle", "skipped"}:
        return memory
    _append_limited(
        memory,
        "bookmarks",
        {
            "bookmark_id": f"bookmark-{uuid4().hex[:10]}",
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "note": note,
            "summary": investigation.get("summary", ""),
            "severity": investigation.get("severity", "info"),
            "queries": investigation.get("queries", [])[:3],
        },
        limit=50,
    )
    return memory


def snapshot_workspace_run(
    memory: dict[str, Any],
    *,
    question: str,
    intent: str,
    sql: str,
    rows: int,
    workflow_trace: list[dict[str, Any]],
    telemetry: dict[str, Any],
    insights: dict[str, Any],
    investigation: dict[str, Any],
    semantic_memory: dict[str, Any],
) -> dict[str, Any]:
    timestamp = datetime.now().isoformat(timespec="seconds")
    run_id = f"run-{timestamp}"
    _append_limited(
        memory,
        "query_history",
        {"run_id": run_id, "question": question, "intent": intent, "sql": sql, "rows": rows, "timestamp": timestamp},
    )
    _append_limited(
        memory,
        "workflow_runs",
        {"run_id": run_id, "trace": workflow_trace[-12:], "status": workflow_trace[-1].get("status") if workflow_trace else "unknown"},
    )
    if investigation and investigation.get("status") not in {None, "idle"}:
        _append_limited(memory, "investigations", {"run_id": run_id, **investigation}, limit=25)
    if insights and insights.get("findings"):
        _append_limited(memory, "generated_insights", {"run_id": run_id, **insights}, limit=25)
    if telemetry:
        _append_limited(
            memory,
            "telemetry_summaries",
            {
                "run_id": run_id,
                "total_tokens": telemetry.get("total_tokens", 0),
                "latency_ms": telemetry.get("latency_ms", 0),
                "cost_usd": telemetry.get("cost_usd", 0.0),
                "model": telemetry.get("model", ""),
            },
        )
    session = start_workspace_session(memory)
    append_session_transcript(
        memory,
        session_id=session["session_id"],
        transcript={
            "run_id": run_id,
            "workflow_id": telemetry.get("workflow_id") or telemetry.get("correlation_id"),
            "question": question,
            "intent": intent,
            "sql": sql,
            "rows": rows,
            "trace": workflow_trace[-12:],
            "telemetry": {
                "correlation_id": telemetry.get("correlation_id"),
                "latency_ms": telemetry.get("latency_ms", 0),
                "total_tokens": telemetry.get("total_tokens", 0),
                "cost_usd": telemetry.get("cost_usd", 0.0),
                "error_type": telemetry.get("error_type"),
            },
            "timestamp": timestamp,
        },
    )
    memory["semantic_dataset_memory"] = semantic_memory or {}
    return memory


def retrieve_workspace_context(memory: dict[str, Any], question: str, limit: int = 3) -> list[dict[str, Any]]:
    terms = {term for term in re.findall(r"[a-z0-9]+", question.lower()) if len(term) > 2}
    scored = []
    seen = set()
    for item in memory.get("query_history", []):
        haystack = f"{item.get('question', '')} {item.get('intent', '')} {item.get('sql', '')}".lower()
        score = sum(1 for term in terms if term in haystack)
        identity = (item.get("question", ""), item.get("sql", ""))
        if score and identity not in seen:
            seen.add(identity)
            confidence = round(min(0.95, max(0.35, score / max(len(terms), 1))), 2)
            scored.append((score, {**item, "retrieval_score": score, "retrieval_confidence": confidence}))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    if scored:
        return [item for _, item in scored[:limit]]
    fallback = []
    for item in reversed(memory.get("query_history", [])[-limit:]):
        fallback.append({**item, "retrieval_score": 0, "retrieval_confidence": 0.25})
    return fallback


def workspace_prompt_block(memory: dict[str, Any] | None, question: str = "") -> str:
    if not memory:
        return ""
    relevant = retrieve_workspace_context(memory, question)
    history_text = "\n".join(
        f"- {item.get('question', '')}: {item.get('sql', '')}" for item in relevant if item.get("sql")
    )
    semantic_keys = ", ".join((memory.get("semantic_dataset_memory") or {}).keys()) or "None"
    return (
        "\n\nWorkspace memory context:\n"
        f"Workspace: {memory.get('workspace_id', 'unknown')} / Team: {memory.get('team_id', 'unknown')}\n"
        f"Relevant prior queries:\n{history_text or '- None'}\n"
        f"Persisted semantic datasets: {semantic_keys}"
    )
