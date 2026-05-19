from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Literal
from uuid import uuid4


ScheduleStatus = Literal["active", "paused", "disabled"]
ScheduleKind = Literal["workflow", "investigation", "telemetry_scan", "schema_drift_scan"]


@dataclass(frozen=True)
class ScheduledWorkflow:
    schedule_id: str
    name: str
    kind: ScheduleKind
    expression: str
    question: str
    status: ScheduleStatus = "active"
    workspace_id: str = "workspace:default"
    timezone_name: str = "UTC"
    owner: str = "Operations"
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["next_run_at"] = next_run_at(self.expression)
        payload["observability"] = schedule_observability(self)
        return payload


def default_schedules(workspace_id: str) -> list[ScheduledWorkflow]:
    return [
        ScheduledWorkflow(
            schedule_id="schedule:daily-executive-briefing",
            name="Daily Executive AI Operations Briefing",
            kind="workflow",
            expression="daily@08:00",
            question="Summarize revenue, anomaly, workflow reliability, and AI spend signals.",
            workspace_id=workspace_id,
            owner="Executive Operations",
            metadata={"priority": "high", "business_domain": "operations"},
        ),
        ScheduledWorkflow(
            schedule_id="schedule:hourly-telemetry-scan",
            name="Hourly Telemetry Degradation Scan",
            kind="telemetry_scan",
            expression="hourly",
            question="Detect runtime degradation, failure clusters, and cost anomalies.",
            workspace_id=workspace_id,
            owner="Platform Engineering",
            metadata={"priority": "medium", "threshold": "failure_rate>10"},
        ),
        ScheduledWorkflow(
            schedule_id="schedule:daily-schema-drift",
            name="Schema Drift Monitor",
            kind="schema_drift_scan",
            expression="daily@06:00",
            question="Inspect schema metadata for drift, freshness, and quality changes.",
            workspace_id=workspace_id,
            owner="Data Platform",
            metadata={"priority": "medium", "business_domain": "data_governance"},
        ),
    ]


def create_schedule(
    *,
    name: str,
    question: str,
    expression: str,
    kind: ScheduleKind = "workflow",
    workspace_id: str = "workspace:default",
    owner: str = "Operations",
) -> ScheduledWorkflow:
    return ScheduledWorkflow(
        schedule_id=f"schedule:{uuid4().hex[:12]}",
        name=name,
        kind=kind,
        expression=expression,
        question=question,
        workspace_id=workspace_id,
        owner=owner,
    )


def next_run_at(expression: str, now: datetime | None = None) -> str | None:
    now = now or datetime.now(timezone.utc)
    expression = expression.strip().lower()
    if expression == "hourly":
        return (now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)).isoformat()
    if expression == "daily":
        return (now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)).isoformat()
    if expression.startswith("every "):
        parts = expression.split()
        if len(parts) == 3 and parts[2] in {"minutes", "minute"}:
            return (now + timedelta(minutes=max(1, int(parts[1])))).isoformat()
        if len(parts) == 3 and parts[2] in {"hours", "hour"}:
            return (now + timedelta(hours=max(1, int(parts[1])))).isoformat()
    if expression.startswith("daily@"):
        hour_text, minute_text = expression.removeprefix("daily@").split(":", 1)
        candidate = now.replace(hour=int(hour_text), minute=int(minute_text), second=0, microsecond=0)
        if candidate <= now:
            candidate += timedelta(days=1)
        return candidate.isoformat()
    return None


def schedule_observability(schedule: ScheduledWorkflow) -> dict[str, Any]:
    priority = schedule.metadata.get("priority", "medium")
    return {
        "status": schedule.status,
        "health": "paused" if schedule.status != "active" else "healthy",
        "priority": priority,
        "sla_minutes": 30 if priority == "high" else 120,
        "emits_telemetry": True,
        "supports_replay": True,
    }


def scheduler_overview(workspace_id: str, schedules: list[ScheduledWorkflow] | None = None) -> dict[str, Any]:
    schedules = schedules or default_schedules(workspace_id)
    rows = [schedule.as_dict() for schedule in schedules]
    return {
        "workspace_id": workspace_id,
        "schedule_count": len(rows),
        "active_count": len([row for row in rows if row["status"] == "active"]),
        "paused_count": len([row for row in rows if row["status"] == "paused"]),
        "schedules": rows,
        "observability": {
            "scheduler_health": "healthy" if all(row["observability"]["health"] == "healthy" for row in rows) else "degraded",
            "telemetry_enabled_count": len([row for row in rows if row["observability"]["emits_telemetry"]]),
        },
    }


__all__ = [
    "ScheduledWorkflow",
    "create_schedule",
    "default_schedules",
    "next_run_at",
    "scheduler_overview",
]
