# Runtime Flow

The production runtime keeps Streamlit, FastAPI, orchestration, model access, and telemetry as separate concerns.

```text
Streamlit workspace
  -> app.py run_query
  -> backend.services.execute_query_workflow
  -> graph.workflow.run_workflow
  -> llm.py OpenAI runtime wrapper
  -> SQLite execution / insight / investigation
  -> telemetry normalization and workspace memory persistence
```

## Correlation

Every workflow telemetry payload is normalized through `backend.telemetry.validate_telemetry_payload`.
That adds:

- `schema_version`
- `correlation_id`
- per-step token, latency, cost, model, and error metadata
- latest OpenAI error fields when present

The correlation ID is intended to connect Streamlit UI exports, terminal logs, and backend diagnostics.

## Request Diagnostics

OpenAI calls are isolated in `llm.py`. The client disables environment proxy trust by default because local proxy variables can mask real API failures as generic connection errors. Set `OPENAI_TRUST_ENV=true` only when a known corporate proxy is required.

## Workflow States

The graph emits lifecycle events for planner, schema retrieval, memory retrieval, SQL generation, validation, reflection, execution, insight generation, and investigation. Streamlit consumes those events for live timelines, agent panels, and telemetry exports.
