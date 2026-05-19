# Orchestration Lifecycle

The analytics runtime models every workflow as a coordinated agent graph. The graph is intentionally lightweight: it captures operational state without forcing the SQL workflow into a heavyweight distributed scheduler.

```text
Planner
  -> Schema Agent
  -> Memory Agent
  -> SQL Agent
  -> Validation Agent
  -> Execution Agent
  -> Insight Agent
  -> Investigation Agent
```

## Agent States

Agents can report:

- `queued`
- `running`
- `retrying`
- `completed`
- `failed`
- `skipped`

Each node records dependency metadata, transition timestamps, confidence, retry count, and operational metadata such as row counts or recovery context.

## Recovery

The workflow uses guarded recovery instead of silent retries:

- validation or execution failures route into reflection when retries remain
- retry exhaustion produces a graceful degradation state
- telemetry keeps the error, retry count, and recovery strategy for operator review

## Confidence

Stage confidence is heuristic by design. It is not a business correctness score. It indicates operational confidence from local signals such as validation success, retries, retrieved memory examples, and execution success.

## Session Replay

Workspace sessions persist transcripts with question, SQL, telemetry, trace, and correlation ID. This supports replay-oriented debugging without re-running model calls.

## Persisted Execution Graphs

FastAPI workflows expose a replayable execution graph through `/workflow/{workflow_id}/execution-graph`.
The response includes:

- DAG nodes and dependency edges
- current node state and dependency readiness
- graph-level completion, failure, retry, and confidence rollups
- replay frames derived from workflow, stage, agent, telemetry, and investigation updates
- workflow metadata for correlation, workspace scoping, and operator drilldown

This gives operators a stable inspection contract for live execution views, replay UI, and orchestration reliability analysis without coupling clients to storage internals.

## Telemetry Aggregation

Workflow telemetry events can be aggregated through `/workflow/{workflow_id}/telemetry/aggregate`.
The aggregation layer groups events by phase, summarizes latency, token usage, estimated cost, failure rate, and failure category. This is the foundation for operational dashboards, incident triage, and future rolling SaaS metrics.
