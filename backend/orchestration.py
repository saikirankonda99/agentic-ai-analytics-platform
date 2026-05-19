from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal


AgentRuntimeStatus = Literal["queued", "running", "retrying", "completed", "failed", "skipped"]


@dataclass(frozen=True)
class AgentNode:
    agent_id: str
    name: str
    phase: str
    dependencies: tuple[str, ...] = ()
    status: AgentRuntimeStatus = "queued"
    queued_at: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    confidence: float = 0.0
    retry_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExecutionGraph:
    graph_id: str
    nodes: tuple[AgentNode, ...]
    edges: tuple[tuple[str, str], ...]
    created_at: str
    updated_at: str


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


DEFAULT_AGENT_SEQUENCE: tuple[tuple[str, str, str, tuple[str, ...]], ...] = (
    ("planner", "Planner", "planner", ()),
    ("schema", "Schema Agent", "schema retrieval", ("planner",)),
    ("memory", "Memory Agent", "memory retrieval", ("schema",)),
    ("sql", "SQL Agent", "sql generation", ("memory",)),
    ("validation", "Validation Agent", "validation", ("sql",)),
    ("reflection", "Reflection Agent", "reflection", ("validation",)),
    ("execution", "Execution Agent", "execution", ("validation",)),
    ("insight", "Insight Agent", "autonomous insight", ("execution",)),
    ("investigation", "Investigation Agent", "investigation", ("insight",)),
)


class OrchestrationCoordinator:
    def build_graph(self, correlation_id: str) -> dict[str, Any]:
        created_at = _now()
        nodes = tuple(
            AgentNode(
                agent_id=agent_id,
                name=name,
                phase=phase,
                dependencies=dependencies,
                queued_at=created_at,
                metadata={"correlation_id": correlation_id},
            )
            for agent_id, name, phase, dependencies in DEFAULT_AGENT_SEQUENCE
        )
        edges = tuple((dependency, agent_id) for agent_id, _, _, dependencies in DEFAULT_AGENT_SEQUENCE for dependency in dependencies)
        return asdict(
            ExecutionGraph(
                graph_id=f"graph-{correlation_id}",
                nodes=nodes,
                edges=edges,
                created_at=created_at,
                updated_at=created_at,
            )
        )

    def transition(
        self,
        graph: dict[str, Any] | None,
        phase: str,
        status: AgentRuntimeStatus,
        *,
        confidence: float | None = None,
        retry_count: int = 0,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not graph:
            graph = self.build_graph("unassigned")
        timestamp = _now()
        nodes = []
        for node in graph.get("nodes", []):
            updated = dict(node)
            if updated.get("phase") == phase:
                updated["status"] = status
                if status == "running" and not updated.get("started_at"):
                    updated["started_at"] = timestamp
                if status in {"completed", "failed", "skipped"}:
                    updated["completed_at"] = timestamp
                if confidence is not None:
                    updated["confidence"] = confidence
                updated["retry_count"] = retry_count
                updated["metadata"] = {**updated.get("metadata", {}), **(metadata or {})}
            nodes.append(updated)
        graph = dict(graph)
        graph["nodes"] = nodes
        graph["updated_at"] = timestamp
        return graph


def stage_confidence(*, status: str, has_error: bool = False, retries: int = 0, signals: int = 1) -> float:
    if has_error or status in {"failed", "error"}:
        return max(0.1, 0.45 - (0.1 * retries))
    if status in {"skipped", "pending"}:
        return 0.5
    base = 0.74 + min(signals, 4) * 0.04
    return round(max(0.0, min(base - retries * 0.08, 0.98)), 2)


def recovery_hint(error: str | None, retry_count: int, max_retries: int) -> dict[str, Any]:
    if not error:
        return {"strategy": "none", "recoverable": False, "message": "No recovery required."}
    if retry_count < max_retries:
        return {
            "strategy": "reflection_retry",
            "recoverable": True,
            "message": "Retry through reflection with prior SQL and runtime error context.",
        }
    return {
        "strategy": "graceful_degradation",
        "recoverable": False,
        "message": "Retries exhausted; preserve trace, telemetry, and error context for operator review.",
    }


default_coordinator = OrchestrationCoordinator()
