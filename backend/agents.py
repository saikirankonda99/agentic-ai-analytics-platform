from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from backend.models import AgentAssignedStage, AgentCoordinationTrace, AgentExecution, WorkflowStage


@dataclass(frozen=True)
class AgentDefinition:
    agent_name: str
    agent_role: str
    assigned_stage: AgentAssignedStage
    handoff_targets: tuple[str, ...] = ()


@dataclass(frozen=True)
class AgentPolicy:
    enable_reflection: bool = True
    enable_anomaly_investigation: bool = True
    enable_executive_briefing: bool = True


@dataclass(frozen=True)
class AgentCoordinationResult:
    executions: tuple[AgentExecution, ...]
    traces: tuple[AgentCoordinationTrace, ...]


class AgentRegistry:
    def __init__(self) -> None:
        self._agents: dict[str, AgentDefinition] = {}
        for agent in _default_agents():
            self.register(agent)

    def register(self, agent: AgentDefinition) -> None:
        self._agents[agent.agent_name] = agent

    def get(self, agent_name: str) -> AgentDefinition:
        return self._agents[agent_name]


class MultiAgentCoordinator:
    def __init__(
        self,
        registry: AgentRegistry | None = None,
        policy: AgentPolicy | None = None,
    ) -> None:
        self.registry = registry or AgentRegistry()
        self.policy = policy or AgentPolicy()

    def coordinate_stage(self, stage: WorkflowStage, question: str) -> AgentCoordinationResult:
        agent_names = list(_stage_agent_plan(stage))
        if stage == "validation" and self.policy.enable_reflection:
            agent_names.append("reflection_agent")
        if stage == "insight_generation" and self.policy.enable_anomaly_investigation:
            agent_names.extend(["anomaly_agent", "investigation_agent"])
        if stage == "insight_generation" and self.policy.enable_executive_briefing:
            agent_names.append("executive_briefing_agent")

        executions = tuple(self._execution(agent_name) for agent_name in agent_names)
        traces = tuple(
            self._handoff_trace(source, target, question)
            for source, target in zip(agent_names, agent_names[1:])
        )
        return AgentCoordinationResult(executions=executions, traces=traces)

    def _execution(self, agent_name: str) -> AgentExecution:
        agent = self.registry.get(agent_name)
        return AgentExecution(
            agent_name=agent.agent_name,
            agent_role=agent.agent_role,
            assigned_stage=agent.assigned_stage,
            agent_status="completed",
        )

    def _handoff_trace(
        self,
        source_agent: str,
        target_agent: str,
        question: str,
    ) -> AgentCoordinationTrace:
        return AgentCoordinationTrace(
            timestamp=datetime.now(timezone.utc).isoformat(),
            source_agent=source_agent,
            target_agent=target_agent,
            handoff_reason="stage_context_handoff",
            context_summary=question[:240],
        )


def _stage_agent_plan(stage: WorkflowStage) -> tuple[str, ...]:
    return {
        "planning": ("planner_agent",),
        "schema_analysis": ("schema_agent",),
        "sql_generation": ("sql_agent",),
        "validation": ("validation_agent",),
        "execution": ("execution_agent",),
        "insight_generation": ("insight_agent",),
    }[stage]


def _default_agents() -> tuple[AgentDefinition, ...]:
    return (
        AgentDefinition("planner_agent", "Workflow planner", "planning", ("schema_agent",)),
        AgentDefinition("schema_agent", "Schema understanding agent", "schema_analysis", ("sql_agent",)),
        AgentDefinition("sql_agent", "SQL generation agent", "sql_generation", ("validation_agent",)),
        AgentDefinition("validation_agent", "Query validation agent", "validation", ("reflection_agent",)),
        AgentDefinition("reflection_agent", "Reflection and self-correction agent", "reflection", ("execution_agent",)),
        AgentDefinition("execution_agent", "Query execution agent", "execution", ("insight_agent",)),
        AgentDefinition("insight_agent", "Insight narration agent", "insight_generation", ("anomaly_agent",)),
        AgentDefinition("anomaly_agent", "Anomaly detection agent", "anomaly_detection", ("investigation_agent",)),
        AgentDefinition("investigation_agent", "Autonomous investigation agent", "investigation", ("executive_briefing_agent",)),
        AgentDefinition("executive_briefing_agent", "Executive briefing generation agent", "executive_briefing"),
    )


__all__ = [
    "AgentCoordinationResult",
    "AgentDefinition",
    "AgentPolicy",
    "AgentRegistry",
    "MultiAgentCoordinator",
]
