from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from backend.persistence import WorkspaceDocument, build_workspace_repository

BASE_DIR = Path(__file__).resolve().parent
WORKSPACE_DIR = BASE_DIR / "data" / "workspaces"

ROLE_CAPABILITIES = {
    "admin": ["query", "monitor", "investigate", "brief", "manage_workspace", "share", "edit_shared"],
    "analyst": ["query", "monitor", "investigate", "brief", "share"],
    "viewer": ["query", "brief"],
}

ONBOARDING_STEPS = [
    {
        "step_id": "workspace_intro",
        "label": "Workspace introduced",
        "description": "Review the workspace map and navigation model.",
    },
    {
        "step_id": "sample_dataset",
        "label": "Sample dataset ready",
        "description": "Use the bundled Chinook dataset or upload a CSV.",
    },
    {
        "step_id": "first_query",
        "label": "First query run",
        "description": "Launch a guided analytics example.",
    },
    {
        "step_id": "results_reviewed",
        "label": "Results reviewed",
        "description": "Inspect the table, SQL, chart, and AI insight brief.",
    },
    {
        "step_id": "export_completed",
        "label": "Export completed",
        "description": "Download a result, report, telemetry bundle, or trace.",
    },
]


def default_user_session() -> dict[str, Any]:
    return {
        "user_id": "local.user",
        "display_name": "Local Analyst",
        "team_id": "default-team",
        "workspace_id": "default-team.local.user",
        "workspace_scope": "personal",
        "workspace_label": "Personal workspace",
        "role": "admin",
        "auth_provider": "local-dev",
        "authenticated": True,
    }


def default_workspace_memory(identity: dict[str, Any] | None = None) -> dict[str, Any]:
    identity = identity or default_user_session()
    return {
        "workspace_id": identity.get("workspace_id", "default-team.local.user"),
        "workspace_scope": identity.get("workspace_scope", "personal"),
        "workspace_label": identity.get("workspace_label", "Personal workspace"),
        "owner_id": identity.get("user_id", "local.user"),
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
        "query_bookmarks": [],
        "pinned_investigations": [],
        "saved_reports": [],
        "recent_activity": [],
        "collaboration_events": [],
        "workspace_preferences": {
            "default_route": "Overview",
            "compact_results": False,
            "last_route": "Overview",
            "preferred_chart_type": "Bar",
            "show_onboarding": True,
        },
        "onboarding": {
            "completed": False,
            "dismissed": False,
            "steps": {item["step_id"]: False for item in ONBOARDING_STEPS},
            "updated_at": None,
        },
        "updated_at": None,
    }


def _safe_id(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9_.-]+", "-", value.strip())
    return value.strip("-") or "default"


def workspace_id(team_id: str, user_id: str) -> str:
    return f"{_safe_id(team_id)}.{_safe_id(user_id)}"


def team_workspace_id(team_id: str) -> str:
    return f"{_safe_id(team_id)}.shared"


def build_user_session(user_id: str, team_id: str, role: str, display_name: str | None = None) -> dict[str, Any]:
    safe_role = role if role in ROLE_CAPABILITIES else "viewer"
    return {
        "user_id": _safe_id(user_id or "local.user"),
        "display_name": display_name or user_id or "Local Analyst",
        "team_id": _safe_id(team_id or "default-team"),
        "workspace_id": workspace_id(team_id or "default-team", user_id or "local.user"),
        "workspace_scope": "personal",
        "workspace_label": "Personal workspace",
        "role": safe_role,
        "auth_provider": "session-local",
        "authenticated": True,
    }


def as_team_workspace(identity: dict[str, Any]) -> dict[str, Any]:
    team_id = identity.get("team_id", "default-team")
    return {
        **identity,
        "workspace_id": team_workspace_id(team_id),
        "workspace_scope": "team",
        "workspace_label": f"{team_id} shared workspace",
    }


def as_personal_workspace(identity: dict[str, Any]) -> dict[str, Any]:
    return {
        **identity,
        "workspace_id": workspace_id(identity.get("team_id", "default-team"), identity.get("user_id", "local.user")),
        "workspace_scope": "personal",
        "workspace_label": "Personal workspace",
    }


def user_can(identity: dict[str, Any] | None, capability: str) -> bool:
    role = (identity or {}).get("role", "viewer")
    return capability in ROLE_CAPABILITIES.get(role, [])


def _workspace_path(workspace_key: str) -> Path:
    WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
    return WORKSPACE_DIR / f"{_safe_id(workspace_key)}.json"


def load_workspace_memory(identity: dict[str, Any]) -> dict[str, Any]:
    try:
        document = build_workspace_repository().get(identity["workspace_id"])
    except Exception:
        document = None
    if document is not None:
        memory = _normalize_workspace_memory(identity, document.memory)
        return memory

    path = _workspace_path(identity["workspace_id"])
    if not path.exists():
        return default_workspace_memory(identity)
    try:
        stored = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        stored = {}
    return _normalize_workspace_memory(identity, stored)


def _normalize_workspace_memory(identity: dict[str, Any], stored: dict[str, Any]) -> dict[str, Any]:
    memory = default_workspace_memory(identity)
    memory.update(stored)
    defaults = default_workspace_memory(identity)
    memory["workspace_preferences"] = {**defaults["workspace_preferences"], **memory.get("workspace_preferences", {})}
    memory["onboarding"] = onboarding_progress({"onboarding": memory.get("onboarding", {})})
    memory.setdefault("members", {}).setdefault(
        identity["user_id"],
        {"display_name": identity.get("display_name", identity["user_id"]), "role": identity.get("role", "viewer")},
    )
    memory.setdefault("collaboration_events", [])
    memory.setdefault("owner_id", identity.get("user_id", "local.user"))
    if memory.get("workspace_id", "").endswith(".shared"):
        memory["workspace_scope"] = "team"
        memory["workspace_label"] = f"{memory.get('team_id', identity.get('team_id', 'default-team'))} shared workspace"
    else:
        memory.setdefault("workspace_scope", identity.get("workspace_scope", "personal"))
        memory.setdefault("workspace_label", identity.get("workspace_label", "Personal workspace"))
    return memory


def load_workspace_memory_by_id(workspace_key: str) -> dict[str, Any]:
    identity = default_user_session()
    identity["workspace_id"] = _safe_id(workspace_key)
    return load_workspace_memory(identity)


def save_workspace_memory(identity: dict[str, Any], memory: dict[str, Any]) -> dict[str, Any]:
    defaults = default_workspace_memory(identity)
    memory = dict(memory or defaults)
    memory["workspace_id"] = identity["workspace_id"]
    memory["team_id"] = identity["team_id"]
    inferred_team_scope = identity["workspace_id"].endswith(".shared")
    memory["workspace_scope"] = "team" if inferred_team_scope else identity.get("workspace_scope", memory.get("workspace_scope", "personal"))
    memory["workspace_label"] = (
        f"{identity['team_id']} shared workspace"
        if inferred_team_scope
        else identity.get("workspace_label", memory.get("workspace_label", "Personal workspace"))
    )
    memory["workspace_preferences"] = {**defaults["workspace_preferences"], **memory.get("workspace_preferences", {})}
    memory["onboarding"] = onboarding_progress(memory)
    memory["updated_at"] = datetime.now().isoformat(timespec="seconds")
    memory.setdefault("members", {})[identity["user_id"]] = {
        "display_name": identity.get("display_name", identity["user_id"]),
        "role": identity.get("role", "viewer"),
    }
    try:
        document = build_workspace_repository().save(
            WorkspaceDocument(
                workspace_id=identity["workspace_id"],
                team_id=identity["team_id"],
                memory=memory,
                updated_at=memory["updated_at"],
            )
        )
        memory["updated_at"] = document.updated_at or memory["updated_at"]
    except Exception:
        _workspace_path(identity["workspace_id"]).write_text(json.dumps(memory, indent=2), encoding="utf-8")
    return memory


def _append_limited(memory: dict[str, Any], key: str, item: dict[str, Any], limit: int = 50) -> None:
    values = list(memory.get(key, []))
    values.append(item)
    memory[key] = values[-limit:]


def workspace_memory_fingerprint(memory: dict[str, Any] | None) -> str:
    payload = dict(memory or {})
    payload.pop("updated_at", None)
    return json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))


def record_workspace_activity(
    memory: dict[str, Any],
    *,
    activity_type: str,
    title: str,
    detail: str = "",
    metadata: dict[str, Any] | None = None,
    actor: dict[str, Any] | None = None,
) -> dict[str, Any]:
    actor = actor or {}
    _append_limited(
        memory,
        "recent_activity",
        {
            "activity_id": f"activity-{uuid4().hex[:10]}",
            "activity_type": activity_type,
            "title": title,
            "detail": detail,
            "metadata": metadata or {},
            "actor_id": actor.get("user_id", ""),
            "actor_name": actor.get("display_name", actor.get("user_id", "")),
            "timestamp": datetime.now().isoformat(timespec="seconds"),
        },
        limit=100,
    )
    return memory


def record_collaboration_event(
    memory: dict[str, Any],
    *,
    event_type: str,
    resource_type: str,
    resource_id: str,
    title: str,
    actor: dict[str, Any] | None = None,
    detail: str = "",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    actor = actor or {}
    event = {
        "event_id": f"collab-{uuid4().hex[:10]}",
        "event_type": event_type,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "title": title,
        "detail": detail,
        "actor_id": actor.get("user_id", ""),
        "actor_name": actor.get("display_name", actor.get("user_id", "")),
        "metadata": metadata or {},
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    }
    _append_limited(memory, "collaboration_events", event, limit=100)
    record_workspace_activity(
        memory,
        activity_type=event_type,
        title=title,
        detail=detail,
        metadata={"resource_type": resource_type, "resource_id": resource_id, **(metadata or {})},
        actor=actor,
    )
    return memory


def shared_metadata(identity: dict[str, Any] | None, visibility: str = "private") -> dict[str, Any]:
    identity = identity or default_user_session()
    timestamp = datetime.now().isoformat(timespec="seconds")
    return {
        "visibility": "team" if visibility == "team" else "private",
        "owner_id": identity.get("user_id", "local.user"),
        "owner_name": identity.get("display_name", identity.get("user_id", "Local Analyst")),
        "created_by": identity.get("user_id", "local.user"),
        "created_by_name": identity.get("display_name", identity.get("user_id", "Local Analyst")),
        "created_at": timestamp,
        "updated_at": timestamp,
        "workspace_scope": identity.get("workspace_scope", "personal"),
    }


def can_edit_resource(identity: dict[str, Any] | None, resource: dict[str, Any] | None) -> bool:
    identity = identity or {}
    resource = resource or {}
    return identity.get("user_id") == resource.get("owner_id") or user_can(identity, "edit_shared")


def onboarding_progress(memory: dict[str, Any]) -> dict[str, Any]:
    onboarding = dict(memory.get("onboarding") or {})
    steps = dict(onboarding.get("steps") or {})
    for item in ONBOARDING_STEPS:
        steps.setdefault(item["step_id"], False)
    completed_count = sum(1 for item in ONBOARDING_STEPS if steps.get(item["step_id"]))
    total = len(ONBOARDING_STEPS)
    onboarding.update(
        {
            "steps": steps,
            "completed_count": completed_count,
            "total_count": total,
            "percent": round((completed_count / total) * 100) if total else 0,
            "completed": completed_count == total,
        }
    )
    return onboarding


def update_onboarding_step(memory: dict[str, Any], step_id: str, completed: bool = True) -> dict[str, Any]:
    if step_id not in {item["step_id"] for item in ONBOARDING_STEPS}:
        return memory
    onboarding = onboarding_progress(memory)
    onboarding["steps"][step_id] = completed
    onboarding["updated_at"] = datetime.now().isoformat(timespec="seconds")
    memory["onboarding"] = onboarding_progress({"onboarding": onboarding})
    record_workspace_activity(
        memory,
        activity_type="onboarding_updated",
        title="Onboarding progress updated",
        detail=step_id,
        metadata={"step_id": step_id, "completed": completed},
    )
    return memory


def dismiss_onboarding(memory: dict[str, Any]) -> dict[str, Any]:
    onboarding = onboarding_progress(memory)
    onboarding["dismissed"] = True
    onboarding["updated_at"] = datetime.now().isoformat(timespec="seconds")
    memory["onboarding"] = onboarding
    record_workspace_activity(
        memory,
        activity_type="onboarding_dismissed",
        title="Onboarding walkthrough dismissed",
        detail="The guided workspace introduction was hidden for this workspace.",
    )
    return memory


def save_workspace_preferences(memory: dict[str, Any], preferences: dict[str, Any]) -> dict[str, Any]:
    current = dict(memory.get("workspace_preferences") or {})
    current.update({key: value for key, value in preferences.items() if value is not None})
    memory["workspace_preferences"] = current
    record_workspace_activity(
        memory,
        activity_type="preferences_saved",
        title="Workspace preferences saved",
        detail=", ".join(sorted(preferences.keys())),
    )
    return memory


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
    record_workspace_activity(memory, activity_type="session_started", title="Workspace session started", detail=session["session_id"])
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


def bookmark_investigation(
    memory: dict[str, Any],
    investigation: dict[str, Any],
    note: str = "",
    *,
    identity: dict[str, Any] | None = None,
    visibility: str = "private",
) -> dict[str, Any]:
    if not investigation or investigation.get("status") in {None, "idle", "skipped"}:
        return memory
    record = {
        **shared_metadata(identity, visibility),
        "bookmark_id": f"bookmark-{uuid4().hex[:10]}",
        "note": note,
        "summary": investigation.get("summary", ""),
        "severity": investigation.get("severity", "info"),
        "queries": investigation.get("queries", [])[:3],
    }
    _append_limited(
        memory,
        "bookmarks",
        record,
        limit=50,
    )
    if visibility == "team":
        record_collaboration_event(memory, event_type="investigation_shared", resource_type="investigation", resource_id=record["bookmark_id"], title="Investigation shared", detail=record["summary"], actor=identity)
    return memory


def pin_investigation(
    memory: dict[str, Any],
    investigation: dict[str, Any],
    note: str = "",
    *,
    identity: dict[str, Any] | None = None,
    visibility: str = "private",
) -> dict[str, Any]:
    if not investigation or investigation.get("status") in {None, "idle", "skipped"}:
        return memory
    record = {
        **shared_metadata(identity, visibility),
        "pin_id": f"pin-{uuid4().hex[:10]}",
        "note": note,
        "summary": investigation.get("summary", ""),
        "severity": investigation.get("severity", "info"),
        "queries": investigation.get("queries", [])[:5],
    }
    _append_limited(
        memory,
        "pinned_investigations",
        record,
        limit=25,
    )
    record_workspace_activity(
        memory,
        activity_type="investigation_pinned",
        title="Investigation pinned",
        detail=investigation.get("summary", ""),
    )
    if visibility == "team":
        record_collaboration_event(memory, event_type="investigation_shared", resource_type="investigation", resource_id=record["pin_id"], title="Investigation pinned to team", detail=record["summary"], actor=identity)
    return memory


def bookmark_query(
    memory: dict[str, Any],
    query: dict[str, Any],
    note: str = "",
    *,
    identity: dict[str, Any] | None = None,
    visibility: str = "private",
) -> dict[str, Any]:
    sql = (query or {}).get("sql", "")
    if not sql.strip():
        return memory
    record = {
        **shared_metadata(identity, visibility),
        "bookmark_id": f"query-{uuid4().hex[:10]}",
        "note": note,
        "question": query.get("question", ""),
        "intent": query.get("intent", query.get("question", "")),
        "sql": sql,
        "rows": query.get("rows", 0),
    }
    _append_limited(
        memory,
        "query_bookmarks",
        record,
        limit=50,
    )
    record_workspace_activity(
        memory,
        activity_type="query_bookmarked",
        title="Query bookmarked",
        detail=query.get("question", "") or sql[:120],
        metadata={"rows": query.get("rows", 0)},
    )
    if visibility == "team":
        record_collaboration_event(memory, event_type="query_shared", resource_type="query_bookmark", resource_id=record["bookmark_id"], title="Query bookmark shared", detail=query.get("question", "") or sql[:120], actor=identity, metadata={"rows": query.get("rows", 0)})
    return memory


def save_report_view(
    memory: dict[str, Any],
    report: dict[str, Any],
    *,
    identity: dict[str, Any] | None = None,
    visibility: str = "private",
) -> dict[str, Any]:
    title = report.get("title") or "Analytics report"
    record = {
        **shared_metadata(identity, visibility),
        "report_id": f"report-{uuid4().hex[:10]}",
        "title": title,
        "scope": report.get("scope", "workspace"),
        "summary": report.get("summary", ""),
        "payload": report.get("payload", {}),
    }
    _append_limited(
        memory,
        "saved_reports",
        record,
        limit=25,
    )
    record_workspace_activity(
        memory,
        activity_type="report_saved",
        title="Report view saved",
        detail=title,
        metadata={"scope": report.get("scope", "workspace")},
    )
    if visibility == "team":
        record_collaboration_event(memory, event_type="report_shared", resource_type="report", resource_id=record["report_id"], title="Report shared", detail=title, actor=identity, metadata={"scope": report.get("scope", "workspace")})
    return memory


def save_investigation_record(
    memory: dict[str, Any],
    investigation: dict[str, Any],
    note: str = "",
    *,
    identity: dict[str, Any] | None = None,
    visibility: str = "private",
) -> dict[str, Any]:
    if not investigation or investigation.get("status") in {None, "idle", "skipped"}:
        return memory
    record = {
        **shared_metadata(identity, visibility),
        "saved_id": f"investigation-{uuid4().hex[:10]}",
        "saved_at": datetime.now().isoformat(timespec="seconds"),
        "note": note,
        **investigation,
    }
    _append_limited(memory, "investigations", record, limit=50)
    record_workspace_activity(
        memory,
        activity_type="investigation_saved",
        title="Investigation saved",
        detail=record.get("summary", ""),
        metadata={"saved_id": record["saved_id"], "severity": record.get("severity", "info"), "note": note},
    )
    if visibility == "team":
        record_collaboration_event(memory, event_type="investigation_shared", resource_type="investigation", resource_id=record["saved_id"], title="Investigation saved to team", detail=record.get("summary", ""), actor=identity)
    return memory


def save_sql_history_record(
    memory: dict[str, Any],
    *,
    question: str,
    sql: str,
    rows: int = 0,
    intent: str = "",
) -> dict[str, Any]:
    if not sql.strip():
        return memory
    _append_limited(
        memory,
        "query_history",
        {
            "run_id": f"manual-{uuid4().hex[:10]}",
            "question": question,
            "intent": intent or question,
            "sql": sql,
            "rows": rows,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "saved": True,
        },
    )
    record_workspace_activity(
        memory,
        activity_type="sql_saved",
        title="SQL saved",
        detail=question or sql[:120],
        metadata={"rows": rows},
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
    update_onboarding_step(memory, "first_query")
    if rows:
        update_onboarding_step(memory, "results_reviewed")
    record_workspace_activity(
        memory,
        activity_type="workflow_completed",
        title="Workflow persisted",
        detail=question,
        metadata={"run_id": run_id, "rows": rows, "status": workflow_trace[-1].get("status") if workflow_trace else "unknown"},
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
