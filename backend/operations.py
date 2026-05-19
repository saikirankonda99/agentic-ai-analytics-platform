from __future__ import annotations

from typing import Any

from backend.telemetry import phase_latency_breakdown, validate_telemetry_payload


def _avg(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def operations_summary(
    *,
    memory: dict[str, Any] | None,
    telemetry: dict[str, Any] | None,
    trace: list[dict[str, Any]] | None,
    execution_graph: dict[str, Any] | None,
    is_executing: bool = False,
) -> dict[str, Any]:
    memory = memory or {}
    telemetry = validate_telemetry_payload(telemetry)
    trace = trace or []
    workflow_runs = memory.get("workflow_runs", [])
    telemetry_runs = memory.get("telemetry_summaries", [])
    investigations = memory.get("investigations", [])
    active_nodes = [
        node
        for node in (execution_graph or {}).get("nodes", [])
        if node.get("status") in {"running", "retrying"}
    ]
    failed_runs = [item for item in telemetry_runs if item.get("error_type")]
    latency_values = [float(item.get("latency_ms", 0) or 0) for item in telemetry_runs]
    cost_values = [float(item.get("cost_usd", 0.0) or 0.0) for item in telemetry_runs]
    token_values = [float(item.get("total_tokens", 0) or 0) for item in telemetry_runs]
    latest_status = trace[-1].get("status", "standby") if trace else "standby"
    return {
        "health": "degraded" if telemetry.get("error_type") else "running" if is_executing else "healthy",
        "active_workflows": 1 if is_executing else 0,
        "active_agents": len(active_nodes),
        "running_investigations": len([item for item in investigations if item.get("status") == "running"]),
        "workflow_throughput": len(workflow_runs),
        "avg_latency_ms": round(_avg(latency_values), 2),
        "latest_latency_ms": telemetry.get("latency_ms", 0),
        "total_tokens": int(sum(token_values) + telemetry.get("total_tokens", 0)),
        "estimated_cost_usd": round(sum(cost_values) + telemetry.get("cost_usd", 0.0), 6),
        "error_rate": round((len(failed_runs) / len(telemetry_runs)) * 100, 2) if telemetry_runs else 0.0,
        "latest_status": latest_status,
        "correlation_id": telemetry.get("correlation_id"),
        "latency_breakdown": phase_latency_breakdown(telemetry),
    }


def agent_utilization(execution_graph: dict[str, Any] | None) -> list[dict[str, Any]]:
    rows = []
    for node in (execution_graph or {}).get("nodes", []):
        rows.append(
            {
                "agent": node.get("name", ""),
                "phase": node.get("phase", ""),
                "status": node.get("status", "queued"),
                "confidence": node.get("confidence", 0.0),
                "retry_count": node.get("retry_count", 0),
                "started_at": node.get("started_at"),
                "completed_at": node.get("completed_at"),
            }
        )
    return rows


def operations_recommendations(summary: dict[str, Any]) -> list[str]:
    recommendations = []
    if summary.get("health") == "degraded":
        recommendations.append("Review OpenAI/runtime diagnostics before launching additional workflows.")
    if summary.get("error_rate", 0) > 20:
        recommendations.append("Inspect failed workflow traces and group errors by phase before expanding usage.")
    if summary.get("avg_latency_ms", 0) > 5000:
        recommendations.append("Profile latency by phase and reduce prompt/context size for the slowest agent.")
    if summary.get("running_investigations", 0):
        recommendations.append("Prioritize active investigation summaries before starting new drill-down work.")
    if not recommendations:
        recommendations.append("Run a workflow or scheduled monitor to populate live operational baselines.")
    return recommendations[:4]
