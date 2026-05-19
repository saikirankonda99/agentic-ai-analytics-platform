from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from backend.models import OrchestrationExecution, WorkflowEvent, WorkflowStreamUpdate


def audit_log_from_workflow(
    workflow: OrchestrationExecution,
    events: tuple[WorkflowEvent, ...] = (),
    updates: tuple[WorkflowStreamUpdate, ...] = (),
) -> dict[str, Any]:
    chain = []
    chain.append(
        {
            "timestamp": workflow.created_at,
            "event_type": "workflow_created",
            "actor": workflow.user_id,
            "resource": workflow.workflow_id,
            "message": f"Workflow created in {workflow.workspace_id}.",
        }
    )
    for event in events:
        chain.append(
            {
                "timestamp": event.timestamp,
                "event_type": event.event_type,
                "actor": "orchestration_runtime",
                "resource": workflow.workflow_id,
                "message": event.message,
            }
        )
    for update in updates:
        chain.append(
            {
                "timestamp": update.timestamp,
                "event_type": update.update_type,
                "actor": "streaming_control_plane",
                "resource": workflow.workflow_id,
                "message": update.message,
            }
        )
    deduped = _dedupe(chain)
    return {
        "workflow_id": workflow.workflow_id,
        "workspace_id": workflow.workspace_id,
        "organization_id": workflow.organization_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "chain_length": len(deduped),
        "lineage": {
            "question": workflow.question,
            "status": workflow.status,
            "current_stage": workflow.current_stage,
            "stage_count": len(workflow.stage_progression),
            "agent_count": len(workflow.agent_executions),
        },
        "audit_chain": deduped,
        "replayable": bool(updates),
    }


def operational_timeline(
    *,
    workflow_audit: dict[str, Any] | None = None,
    incidents: list[dict[str, Any]] | None = None,
    schedules: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    rows = []
    if workflow_audit:
        rows.extend(workflow_audit.get("audit_chain", []))
    for incident in incidents or []:
        rows.append(
            {
                "timestamp": incident.get("created_at"),
                "event_type": "incident",
                "actor": incident.get("source", "incident_engine"),
                "resource": incident.get("incident_id"),
                "message": incident.get("summary", incident.get("title", "")),
            }
        )
    for schedule in schedules or []:
        rows.append(
            {
                "timestamp": schedule.get("next_run_at"),
                "event_type": "scheduled_workflow",
                "actor": schedule.get("owner", "scheduler"),
                "resource": schedule.get("schedule_id"),
                "message": f"Next scheduled execution for {schedule.get('name', 'workflow')}.",
            }
        )
    return sorted([row for row in rows if row.get("timestamp")], key=lambda row: str(row["timestamp"]))


def _dedupe(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str]] = set()
    deduped = []
    for row in rows:
        key = (str(row.get("timestamp")), str(row.get("event_type")), str(row.get("message")))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return sorted(deduped, key=lambda row: str(row.get("timestamp", "")))


__all__ = ["audit_log_from_workflow", "operational_timeline"]
