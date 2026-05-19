# AI Operations Center

The AI Operations Center is the workspace-level control plane for orchestration health, execution telemetry, and agent runtime posture.

## Signals

The view rolls up:

- active workflow count
- active agent count
- running investigation count
- workflow throughput
- rolling latency
- token volume
- estimated runtime cost
- error rate
- latest workflow status

Signals are computed from persisted workspace memory plus the active workflow telemetry payload.

## Execution Center

The execution center shows:

- workflow queue history
- stage progression cards
- agent dependency graph
- retry and recovery state
- confidence scores
- telemetry export controls

## API Support

FastAPI exposes operational inspection endpoints:

```text
GET /operations/summary
GET /workflow/{workflow_id}/telemetry/events
GET /workflow/{workflow_id}/replay
GET /telemetry/schema
```

These endpoints are intentionally read-only and suitable for dashboard polling or external observability adapters.
