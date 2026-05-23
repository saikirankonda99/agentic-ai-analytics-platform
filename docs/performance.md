# Performance Notes

This project keeps performance work practical: optimize repeated render/export work, avoid unnecessary persistence writes, and make slow sections visible before adding more architecture.

## Streamlit Rendering Strategy

- Export payloads are cached by content fingerprint in `st.session_state["_render_export_cache"]`.
- Result CSV exports reuse cached bytes for identical filtered/full result sets.
- Telemetry JSON/CSV exports reuse cached bytes for identical telemetry payloads.
- History, collaboration, report, and activity feeds render bounded recent slices instead of rebuilding full lists.
- Result explorer controls update session state only when values actually change.
- Render timings are stored in `st.session_state["_render_timings"]` and surfaced in the History workspace under `Performance Diagnostics`.

## Persistence Strategy

- Workspace persistence computes a stable fingerprint that ignores `updated_at`.
- `persist_workspace_memory()` skips disk/database writes when the workspace payload has not changed.
- Persistence timings are stored in `st.session_state["workspace_persistence_timings"]`.
- Shared report, bookmark, investigation, and onboarding updates still persist immediately because they change workspace state.

## Orchestration Strategy

- Backend stream update assembly is cached per workflow snapshot.
- The cache key tracks workflow status, current stage, stage/agent/event counts, latest event timestamp, and telemetry totals.
- Cache entries are invalidated when workflows are saved or workflow events are appended.
- API telemetry aggregation continues to read from stream updates, but avoids rebuilding stream update objects for unchanged workflows.

## Troubleshooting Slow Workflows

1. Open `History` and inspect `Performance Diagnostics` for slow render or persistence sections.
2. Check `Operations` for workflow latency, token volume, retry state, and error posture.
3. Check `Agents` for per-phase latency breakdown and SQL validation/recovery signals.
4. For backend workflows, inspect `/workflow/{workflow_id}/telemetry/aggregate`.
5. If startup feels slow, inspect `/diagnostics` and Streamlit health before investigating model latency.

## Future Profiling Targets

- Large result filtering in `Result Explorer`.
- Long workspace histories with many saved reports or investigations.
- Multi-connector schema inspection when external databases are added.
- Model-backed SQL generation and autonomous investigation retry paths.
