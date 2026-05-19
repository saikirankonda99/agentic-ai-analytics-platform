from __future__ import annotations

from backend.orchestration import OrchestrationCoordinator, recovery_hint, stage_confidence


def test_coordinator_tracks_dependencies_and_transitions() -> None:
    coordinator = OrchestrationCoordinator()
    graph = coordinator.build_graph("wf-test")
    graph = coordinator.transition(graph, "sql generation", "running", confidence=0.72)
    graph = coordinator.transition(graph, "sql generation", "completed", confidence=0.91)

    sql_node = next(item for item in graph["nodes"] if item["phase"] == "sql generation")

    assert graph["graph_id"] == "graph-wf-test"
    assert ("memory", "sql") in [tuple(edge) for edge in graph["edges"]]
    assert sql_node["status"] == "completed"
    assert sql_node["started_at"] is not None
    assert sql_node["completed_at"] is not None
    assert sql_node["confidence"] == 0.91


def test_confidence_and_recovery_hints_are_bounded() -> None:
    assert 0 <= stage_confidence(status="completed", signals=3) <= 1
    assert recovery_hint("bad sql", 0, 2)["recoverable"] is True
    assert recovery_hint("bad sql", 2, 2)["strategy"] == "graceful_degradation"


def test_coordinator_reports_runnable_nodes_and_summary() -> None:
    coordinator = OrchestrationCoordinator()
    graph = coordinator.build_graph("wf-test")

    assert [node["phase"] for node in coordinator.runnable_nodes(graph)] == ["planner"]

    graph = coordinator.transition(graph, "planner", "completed", confidence=0.9)
    summary = coordinator.graph_summary(graph)

    assert "schema retrieval" in summary["runnable"]
    assert summary["completed"] == 1
    assert summary["completion_rate"] > 0
    assert summary["critical_path"][0] == "planner"
