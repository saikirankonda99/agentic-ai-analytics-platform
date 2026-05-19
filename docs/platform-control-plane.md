# Platform Control Plane

The analytics runtime exposes a lightweight control plane for orchestration policy, workspace inspection, and operational recommendation surfaces. These additions keep the Streamlit and FastAPI architecture intact while making workflow behavior easier to inspect and govern.

## Execution Policy

`backend.policies` defines the runtime execution policy used by workflow nodes and diagnostics:

- `ORCHESTRATION_MAX_RETRIES` controls retry budget decisions.
- `ORCHESTRATION_CONFIDENCE_FLOOR` controls low-confidence monitoring signals.
- `ORCHESTRATION_ENABLE_FALLBACK_MODEL` records whether guarded model fallback is allowed.
- `ORCHESTRATION_ENABLE_INVESTIGATION` records whether failed or low-confidence workflows should feed investigation workflows.
- `ORCHESTRATION_MAX_RESULT_ROWS` sets the default result-size policy boundary.

Workflow failures attach a `policy_decision` with the stage, action, reason, confidence, retry count, and configured thresholds. This keeps retry and degradation behavior explicit without replacing the current orchestration flow.

## Workspace Inspection

`backend.workspace_inspection` converts persisted workspace memory into SaaS-style inspection payloads:

- workspace, member, query, workflow, investigation, bookmark, and session counts
- transcript counts and active session identity
- semantic memory category counts
- telemetry totals, average latency, estimated cost, token totals, and error rate
- saved SQL history and transcript export rows

The FastAPI runtime exposes:

- `GET /workspace/{workspace_id}/inspection`
- `GET /workspace/{workspace_id}/transcripts`
- `GET /workspace/{workspace_id}/sql-history`

The Streamlit API workspace mirrors these surfaces and provides a JSON workspace report export.

## Autonomous Recommendations

`backend.recommendations` turns operations, telemetry, memory, and investigation state into structured recommendation cards. Recommendations are deterministic and testable, which allows the UI to show follow-up questions, anomaly alerts, optimization actions, schema-memory prompts, and investigation escalation suggestions without coupling the UI to ad hoc business logic.

## Operational Benefit

These modules separate platform control-plane concerns from presentation code:

- policy evaluation can be tested independently from model execution
- workspace inspection can back both Streamlit exports and API consumers
- recommendations can evolve without rewriting dashboard layouts
- diagnostics include policy posture, making runtime decisions easier to audit
