from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4


IncidentSeverity = Literal["info", "warning", "critical"]
IncidentStatus = Literal["open", "acknowledged", "resolved"]


@dataclass(frozen=True)
class OperationalIncident:
    incident_id: str
    title: str
    severity: IncidentSeverity
    status: IncidentStatus
    source: str
    created_at: str
    summary: str
    correlation_id: str | None = None
    workflow_id: str | None = None
    telemetry: dict[str, Any] = field(default_factory=dict)
    escalation: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def severity_from_signal(*, failure_rate: float = 0.0, latency_ms: int = 0, cost_usd: float = 0.0) -> IncidentSeverity:
    if failure_rate >= 25 or latency_ms >= 15000 or cost_usd >= 5:
        return "critical"
    if failure_rate >= 10 or latency_ms >= 5000 or cost_usd >= 1:
        return "warning"
    return "info"


def incident_from_telemetry(
    telemetry: dict[str, Any] | None,
    *,
    workflow_id: str | None = None,
    source: str = "telemetry_monitor",
) -> OperationalIncident | None:
    telemetry = telemetry or {}
    failure_rate = float(telemetry.get("failure_rate", 0.0) or 0.0)
    latency_ms = int(telemetry.get("latency_ms", 0) or 0)
    cost_usd = float(telemetry.get("cost_usd", 0.0) or 0.0)
    error_type = telemetry.get("error_type")
    severity = severity_from_signal(failure_rate=failure_rate, latency_ms=latency_ms, cost_usd=cost_usd)
    if severity == "info" and not error_type:
        return None
    title = "Workflow runtime degradation detected" if severity != "info" else "Workflow error signal detected"
    return OperationalIncident(
        incident_id=f"incident:{uuid4().hex[:12]}",
        title=title,
        severity=severity,
        status="open",
        source=source,
        created_at=datetime.now(timezone.utc).isoformat(),
        summary=_incident_summary(failure_rate, latency_ms, cost_usd, error_type),
        correlation_id=telemetry.get("correlation_id"),
        workflow_id=workflow_id or telemetry.get("workflow_id"),
        telemetry=telemetry,
        escalation=escalation_policy(severity),
    )


def escalation_policy(severity: IncidentSeverity) -> dict[str, Any]:
    if severity == "critical":
        return {"channel": "operations_lead", "sla_minutes": 15, "requires_executive_visibility": True}
    if severity == "warning":
        return {"channel": "platform_oncall", "sla_minutes": 60, "requires_executive_visibility": False}
    return {"channel": "operations_log", "sla_minutes": 240, "requires_executive_visibility": False}


def incident_timeline(incidents: list[OperationalIncident] | None = None) -> list[dict[str, Any]]:
    return [
        {
            "timestamp": incident.created_at,
            "event_type": "incident_created",
            "severity": incident.severity,
            "status": incident.status,
            "title": incident.title,
            "incident_id": incident.incident_id,
            "workflow_id": incident.workflow_id,
        }
        for incident in incidents or []
    ]


def incident_overview(incidents: list[OperationalIncident] | None = None) -> dict[str, Any]:
    incidents = incidents or []
    return {
        "incident_count": len(incidents),
        "open_count": len([item for item in incidents if item.status == "open"]),
        "critical_count": len([item for item in incidents if item.severity == "critical"]),
        "warning_count": len([item for item in incidents if item.severity == "warning"]),
        "timeline": incident_timeline(incidents),
        "incidents": [incident.as_dict() for incident in incidents],
    }


def _incident_summary(failure_rate: float, latency_ms: int, cost_usd: float, error_type: str | None) -> str:
    signals = []
    if failure_rate:
        signals.append(f"failure rate {failure_rate:.2f}%")
    if latency_ms:
        signals.append(f"latency {latency_ms} ms")
    if cost_usd:
        signals.append(f"estimated cost ${cost_usd:.4f}")
    if error_type:
        signals.append(f"error {error_type}")
    return "Runtime signal crossed alert policy: " + ", ".join(signals)


__all__ = [
    "OperationalIncident",
    "escalation_policy",
    "incident_from_telemetry",
    "incident_overview",
    "incident_timeline",
    "severity_from_signal",
]
