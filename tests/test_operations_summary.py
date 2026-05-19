from __future__ import annotations

from backend.operations import agent_utilization, operations_recommendations, operations_summary


def test_operations_summary_rolls_up_workspace_metrics() -> None:
    summary = operations_summary(
        memory={
            "workflow_runs": [{"status": "success"}],
            "telemetry_summaries": [{"latency_ms": 100, "cost_usd": 0.01, "total_tokens": 50}],
            "investigations": [{"status": "running"}],
        },
        telemetry={"steps": [{"step": "sql generation", "latency_ms": 20, "total_tokens": 10}]},
        trace=[{"status": "success"}],
        execution_graph={"nodes": [{"name": "SQL Agent", "phase": "sql generation", "status": "running"}]},
        is_executing=True,
    )

    assert summary["active_workflows"] == 1
    assert summary["active_agents"] == 1
    assert summary["running_investigations"] == 1
    assert summary["workflow_throughput"] == 1
    assert summary["total_tokens"] == 60


def test_agent_utilization_and_recommendations() -> None:
    rows = agent_utilization({"nodes": [{"name": "Planner", "phase": "planner", "status": "completed"}]})
    recommendations = operations_recommendations({"health": "degraded", "error_rate": 25})

    assert rows[0]["agent"] == "Planner"
    assert recommendations
