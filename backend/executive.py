from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def executive_scorecard(
    *,
    governance: dict[str, Any] | None = None,
    scheduler: dict[str, Any] | None = None,
    telemetry: dict[str, Any] | None = None,
    incidents: dict[str, Any] | None = None,
) -> dict[str, Any]:
    governance = governance or {}
    scheduler = scheduler or {}
    telemetry = telemetry or {}
    incidents = incidents or {}
    governance_summary = governance.get("summary", {})
    readiness_score = _readiness_score(governance_summary, scheduler, telemetry, incidents)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "readiness_score": readiness_score,
        "readiness_status": _readiness_status(readiness_score),
        "kpis": {
            "trusted_datasets": governance_summary.get("trusted_count", 0),
            "dataset_count": governance_summary.get("dataset_count", 0),
            "active_schedules": scheduler.get("active_count", 0),
            "workflow_failure_rate": telemetry.get("failure_rate", 0.0),
            "estimated_ai_cost_usd": telemetry.get("cost_usd", 0.0),
            "open_incidents": incidents.get("open_count", 0),
            "critical_incidents": incidents.get("critical_count", 0),
        },
        "narrative": _executive_narrative(readiness_score, governance_summary, scheduler, telemetry, incidents),
        "actions": _executive_actions(governance_summary, scheduler, telemetry, incidents),
    }


def operational_report(
    *,
    workspace_id: str,
    governance: dict[str, Any],
    scheduler: dict[str, Any],
    telemetry: dict[str, Any],
    incidents: dict[str, Any],
) -> dict[str, Any]:
    scorecard = executive_scorecard(
        governance=governance,
        scheduler=scheduler,
        telemetry=telemetry,
        incidents=incidents,
    )
    return {
        "workspace_id": workspace_id,
        "report_type": "ai_data_operations",
        "generated_at": scorecard["generated_at"],
        "scorecard": scorecard,
        "sections": [
            {
                "title": "Governance",
                "summary": f"{governance.get('summary', {}).get('trusted_count', 0)} trusted dataset(s) out of {governance.get('summary', {}).get('dataset_count', 0)} registered.",
                "payload": governance.get("summary", {}),
            },
            {
                "title": "Autonomous Monitoring",
                "summary": f"{scheduler.get('active_count', 0)} active scheduled workflow(s).",
                "payload": scheduler.get("observability", {}),
            },
            {
                "title": "Operational Incidents",
                "summary": f"{incidents.get('open_count', 0)} open incident(s), {incidents.get('critical_count', 0)} critical.",
                "payload": incidents,
            },
        ],
        "export_ready": True,
    }


def _readiness_score(
    governance_summary: dict[str, Any],
    scheduler: dict[str, Any],
    telemetry: dict[str, Any],
    incidents: dict[str, Any],
) -> int:
    score = 72
    score += min(int(governance_summary.get("trusted_count", 0)) * 4, 12)
    score += min(int(scheduler.get("active_count", 0)) * 3, 9)
    score -= int(float(telemetry.get("failure_rate", 0.0) or 0.0) // 5) * 4
    score -= int(incidents.get("critical_count", 0)) * 12
    score -= int(incidents.get("warning_count", 0)) * 4
    return max(0, min(score, 100))


def _readiness_status(score: int) -> str:
    if score >= 85:
        return "strong"
    if score >= 70:
        return "stable"
    if score >= 50:
        return "watch"
    return "at_risk"


def _executive_narrative(
    readiness_score: int,
    governance_summary: dict[str, Any],
    scheduler: dict[str, Any],
    telemetry: dict[str, Any],
    incidents: dict[str, Any],
) -> str:
    return (
        f"AI data operations readiness is {_readiness_status(readiness_score)} at {readiness_score}. "
        f"The platform tracks {governance_summary.get('dataset_count', 0)} governed dataset(s), "
        f"{scheduler.get('active_count', 0)} active scheduled monitor(s), "
        f"{telemetry.get('failure_rate', 0.0)}% workflow failure rate, and "
        f"{incidents.get('open_count', 0)} open incident(s)."
    )


def _executive_actions(
    governance_summary: dict[str, Any],
    scheduler: dict[str, Any],
    telemetry: dict[str, Any],
    incidents: dict[str, Any],
) -> list[str]:
    actions = []
    if governance_summary.get("review_required_count", 0):
        actions.append("Complete dataset ownership and approval review for datasets awaiting governance signoff.")
    if scheduler.get("active_count", 0) == 0:
        actions.append("Activate recurring telemetry and schema monitoring schedules.")
    if telemetry.get("failure_rate", 0.0) > 10:
        actions.append("Review workflow failure clusters and assign remediation owners.")
    if incidents.get("critical_count", 0):
        actions.append("Escalate critical incidents through the operations response workflow.")
    if not actions:
        actions.append("Maintain weekly executive review of AI spend, reliability, and governed dataset coverage.")
    return actions


__all__ = ["executive_scorecard", "operational_report"]
