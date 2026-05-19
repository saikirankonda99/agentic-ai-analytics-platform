# Production Architecture Notes

This platform is intentionally kept modular so it can evolve from a local analytics workspace into a SaaS analytics control plane without replacing Streamlit or FastAPI.

## Frontend Boundary

Streamlit remains the operator workspace. It owns:

- workspace route state
- command submission
- telemetry export controls
- investigation, monitoring, agents, API, copilot, and history views

The UI does not call OpenAI directly. Model access stays behind `llm.py`.

## Backend Boundary

FastAPI owns lifecycle APIs, readiness, diagnostics, workflow persistence, account/workspace scoping, and stream endpoints. The `/diagnostics` endpoint intentionally reports configuration posture rather than secrets.

## Orchestration Boundary

`graph.workflow` owns deterministic workflow phases. It is responsible for validation, retry/reflection routing, telemetry aggregation, and error-safe workflow results.

## Telemetry Boundary

`backend.telemetry` is the shared schema layer. It normalizes untrusted telemetry dictionaries before UI export, backend caching, or test assertions.

## Current SaaS Readiness

Implemented:

- workspace isolation primitives
- role capability checks
- lifecycle tracing
- structured OpenAI diagnostics
- telemetry export
- workflow persistence scaffolding

Remaining before production:

- external auth provider
- managed database migrations
- background queue workers
- tenant-level rate limits
- audit log retention controls
- secrets manager integration
