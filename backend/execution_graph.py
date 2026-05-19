from __future__ import annotations

from datetime import datetime
from typing import Any

from backend.models import OrchestrationExecution, WorkflowStreamUpdate
from backend.orchestration import default_coordinator, stage_confidence


STAGE_TO_PHASE = {
    "planning": "planner",
    "schema_analysis": "schema retrieval",
    "sql_generation": "sql generation",
    "validation": "validation",
    "execution": "execution",
    "insight_generation": "autonomous insight",
}


def execution_graph_from_workflow(workflow: OrchestrationExecution) -> dict[str, Any]:
    graph = default_coordinator.build_graph(workflow.workflow_id.replace("workflow:", "wf-"))
    for stage in workflow.stage_progression:
        phase = STAGE_TO_PHASE.get(stage.stage)
        if not phase:
            continue
        graph = default_coordinator.transition(
            graph,
            phase,
            stage.status,
            confidence=stage_confidence(status=stage.status, signals=2),
            metadata={
                "workflow_id": workflow.workflow_id,
                "workflow_stage": stage.stage,
                "transition_timestamp": stage.timestamp,
            },
        )

    if workflow.status in {"completed", "failed"}:
        graph = _mark_terminal_optional_nodes(graph)
    graph["metadata"] = {
        **graph.get("metadata", {}),
        "workflow_id": workflow.workflow_id,
        "workflow_status": workflow.status,
        "workspace_id": workflow.workspace_id,
        "organization_id": workflow.organization_id,
        "current_stage": workflow.current_stage,
        "replay_supported": True,
    }
    graph["summary"] = default_coordinator.graph_summary(graph)
    graph["dependency_status"] = dependency_status(graph)
    return graph


def dependency_status(graph: dict[str, Any]) -> list[dict[str, Any]]:
    nodes = {node.get("agent_id"): node for node in graph.get("nodes", [])}
    rows = []
    for node in graph.get("nodes", []):
        dependencies = list(node.get("dependencies", []))
        blocked_by = [
            dependency
            for dependency in dependencies
            if nodes.get(dependency, {}).get("status") not in {"completed", "skipped"}
        ]
        rows.append(
            {
                "agent_id": node.get("agent_id"),
                "phase": node.get("phase"),
                "status": node.get("status"),
                "dependencies": dependencies,
                "blocked_by": blocked_by,
                "ready": node.get("status") == "queued" and not blocked_by,
            }
        )
    return rows


def replay_frames_from_updates(updates: tuple[WorkflowStreamUpdate, ...]) -> list[dict[str, Any]]:
    frames = []
    for index, update in enumerate(updates, start=1):
        payload = dict(update.payload)
        frames.append(
            {
                "sequence": index,
                "timestamp": update.timestamp,
                "update_type": update.update_type,
                "phase": payload.get("stage") or payload.get("assigned_stage") or payload.get("event_type") or update.update_type,
                "status": payload.get("status") or payload.get("agent_status") or update.update_type,
                "message": update.message,
                "elapsed_ms_from_previous": _elapsed_ms(frames[-1]["timestamp"], update.timestamp) if frames else 0,
                "payload": payload,
            }
        )
    return frames


def execution_graph_response(
    workflow: OrchestrationExecution,
    updates: tuple[WorkflowStreamUpdate, ...] = (),
) -> dict[str, Any]:
    graph = execution_graph_from_workflow(workflow)
    replay_frames = replay_frames_from_updates(updates)
    return {
        "workflow_id": workflow.workflow_id,
        "graph": graph,
        "summary": graph["summary"],
        "dependency_status": graph["dependency_status"],
        "replay": {
            "supported": True,
            "frame_count": len(replay_frames),
            "frames": replay_frames,
        },
    }


def _mark_terminal_optional_nodes(graph: dict[str, Any]) -> dict[str, Any]:
    updated_nodes = []
    for node in graph.get("nodes", []):
        updated = dict(node)
        if updated.get("status") == "queued" and updated.get("phase") in {"reflection", "investigation"}:
            updated["status"] = "skipped"
            updated["completed_at"] = graph.get("updated_at")
            updated["confidence"] = stage_confidence(status="skipped")
        updated_nodes.append(updated)
    return {**graph, "nodes": updated_nodes}


def _elapsed_ms(previous: str, current: str) -> int:
    try:
        previous_dt = datetime.fromisoformat(previous)
        current_dt = datetime.fromisoformat(current)
    except ValueError:
        return 0
    return max(int((current_dt - previous_dt).total_seconds() * 1000), 0)


__all__ = [
    "dependency_status",
    "execution_graph_from_workflow",
    "execution_graph_response",
    "replay_frames_from_updates",
]
