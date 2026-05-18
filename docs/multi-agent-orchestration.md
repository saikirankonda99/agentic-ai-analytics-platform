# Multi-Agent Orchestration Design

The backend now models analytics execution as a coordinated multi-agent workflow while preserving the existing REST, SSE, websocket, telemetry, persistence, and vector-memory boundaries.

## Agent Layers

- `backend.agents.AgentRegistry` defines available specialist agents.
- `backend.agents.AgentPolicy` controls lightweight autonomous behaviors.
- `backend.agents.MultiAgentCoordinator` maps workflow stages to agent executions and handoffs.
- `backend.services.OrchestrationService` persists workflow state, agent executions, events, traces, telemetry, and memory.
- `backend.runtime.OrchestrationRuntime` remains the asynchronous execution boundary and websocket broadcaster.

## Specialist Agents

The current registry includes:

- planner
- schema understanding
- SQL generation
- validation
- reflection and self-correction
- query execution
- insight narration
- anomaly detection
- autonomous investigation
- executive briefing generation

These agents are simulated today, but the registry and policy objects are designed to become tool-calling or distributed worker entrypoints.

## Coordination Traces

Agent handoffs are persisted as execution traces with:

- source agent
- target agent
- handoff reason
- context summary
- timestamp

The traces give the dashboard and operators a durable view into inter-agent coordination without requiring full agent autonomy yet.

## Autonomous Investigation Chain

During `insight_generation`, the anomaly agent can trigger a lightweight investigation chain. The system records:

- agent executions for anomaly detection, investigation, and executive briefing
- handoff traces
- workflow events
- workspace-scoped vector-memory records
- websocket/SSE-compatible updates

## Future Extensions

The current design prepares for:

- tool calling per agent
- planner loops
- long-term memory retrieval
- Redis-backed fanout
- Celery/RQ/distributed workers
- human approval checkpoints
- richer autonomous monitoring jobs
