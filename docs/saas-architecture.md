# SaaS Architecture

The backend is organized around explicit organization and workspace boundaries while preserving the current Streamlit-facing API contracts.

## Tenant Context

Requests may provide `x-user-id`, `x-organization-id`, and `x-workspace-id` headers. The auth-ready session layer converts those headers into lightweight user, organization, workspace, and workspace membership domain models. Missing headers fall back to the default anonymous workspace so local development and the current frontend continue to work.

## Scoped Runtime State

Workflow state, telemetry, workflow events, agent execution metadata, agent traces, vector memory, and usage accounting carry organization and workspace identifiers. The current runtime remains in-process and lightweight, but repository boundaries keep the storage model ready for multi-tenant Postgres, Redis coordination, and distributed workers.

## Usage Accounting

Usage tracking records lightweight accounting events for API requests, workflow executions, token usage, and estimated AI cost. These records are persisted behind a `UsageStorage` abstraction so future Stripe billing, subscription plans, RBAC enforcement, and usage quotas can be added without changing orchestration code paths.

## Auth And Billing Readiness

The middleware and request dependency are intentionally provider-neutral. OAuth/SSO can later replace header-derived identities, while existing organization, workspace, membership, and usage repositories provide the foundation for plan management and billing integration.
