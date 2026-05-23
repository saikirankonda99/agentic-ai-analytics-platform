# Documentation Index

This directory contains architecture, deployment, testing, and operations notes for the Agentic AI Analytics Platform.

## Primary Docs

| Document | Purpose |
|---|---|
| [Architecture Diagrams](architecture.md) | Mermaid diagrams for frontend/backend interaction, orchestration, SQL intelligence, persistence, collaboration, telemetry, and E2E flow |
| [Demo Walkthrough](demo-walkthrough.md) | Concise demo script, timing, recommended datasets, and screenshot order |
| [Collaboration Workflows](collaboration.md) | Personal/team workspace switching, shared resources, activity history, and lightweight permissions |
| [Performance Notes](performance.md) | Render caching, persistence write reduction, orchestration update caching, and slow workflow troubleshooting |
| [Screenshots Guide](../screenshots/README.md) | Screenshot folders, naming conventions, and capture guidance |
| [Deployment](deployment.md) | Docker, persistence, health checks, and runtime boundaries |
| [PostgreSQL Persistence](postgresql-persistence.md) | SQLite/PostgreSQL configuration and migration posture |
| [E2E Testing](e2e-testing.md) | Playwright setup, CI execution, artifacts, debugging |
| [Troubleshooting](troubleshooting.md) | Common local runtime and OpenAI issues |

## System Areas

| Document | Area |
|---|---|
| [Enterprise Platform Overview](enterprise-platform-overview.md) | Full platform architecture and runtime overview |
| [Platform Control Plane](platform-control-plane.md) | FastAPI operations, diagnostics, telemetry, governance boundaries |
| [Orchestration Lifecycle](orchestration-lifecycle.md) | Workflow phases and lifecycle state |
| [Multi-Agent Orchestration](multi-agent-orchestration.md) | Agent execution model and handoff metadata |
| [SQL Intelligence](sql-intelligence.md) | SQL validation, explanation, recovery, and quality checks |
| [Connectors](connectors.md) | Connector registry, health, schema, and validation endpoints |
| [Usability Onboarding](usability-onboarding.md) | Workspace onboarding and operator flow |

## Supporting Notes

| Document | Purpose |
|---|---|
| [CI/CD Runtime Validation](cicd-runtime-validation.md) | GitHub Actions workflow contract |
| [Production Hardening](production-hardening.md) | Startup validation and production checks |
| [Runtime Flow](runtime-flow.md) | Runtime execution details |
| [Production Architecture](production-architecture.md) | Deployment-oriented architecture notes |
| [SaaS Architecture](saas-architecture.md) | Multi-tenant and persistence direction |
| [AI Operations Center](ai-operations-center.md) | Operations workspace notes |
| [Enterprise Data Operations](enterprise-data-operations.md) | Data operations posture |

These supporting notes preserve implementation history and deeper design context. The canonical presentation path for GitHub readers is the root README, this index, `architecture.md`, `demo-walkthrough.md`, `collaboration.md`, `deployment.md`, and `e2e-testing.md`.

## Maintenance Notes

- Keep the README concise and link to this directory for detail.
- Prefer Mermaid diagrams in `architecture.md` for GitHub rendering.
- Keep E2E instructions in `e2e-testing.md`; do not duplicate full setup elsewhere.
- Keep deployment details in `deployment.md` and persistence details in `postgresql-persistence.md`.
