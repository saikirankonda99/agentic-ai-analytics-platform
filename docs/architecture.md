# Architecture Diagrams

This page collects the primary architecture diagrams for the Agentic AI Analytics Platform. The diagrams are written in Mermaid so they render directly in GitHub Markdown.

## Frontend And Backend Interaction

```mermaid
flowchart LR
    user[Operator or analyst] --> streamlit[Streamlit workspace]
    streamlit --> views[ui/views modules]
    streamlit --> localRuntime[Local workflow runner]
    streamlit --> fastapi[FastAPI control plane]

    fastapi --> auth[Auth sessions]
    fastapi --> connectors[Connector registry]
    fastapi --> diagnostics[Startup and runtime diagnostics]
    fastapi --> workspaceApi[Workspace APIs]
    fastapi --> workflowApi[Workflow APIs]

    localRuntime --> orchestration[Orchestration runtime]
    workflowApi --> orchestration
    orchestration --> llm[OpenAI runtime abstraction]
    orchestration --> sql[SQL validation and execution]
    orchestration --> telemetry[Telemetry normalization]
    orchestration --> persistence[Persistence repositories]
```

## Orchestration Workflow

```mermaid
flowchart TD
    start[User question] --> planner[Planner]
    planner --> schema[Schema retrieval]
    schema --> memory[Memory retrieval]
    memory --> generation[SQL generation]
    generation --> validation[SQL validation]
    validation -->|valid| execution[Query execution]
    validation -->|invalid and retryable| reflection[Reflection and recovery]
    reflection --> generation
    validation -->|blocked| failure[Graceful failure state]
    execution --> insight[Autonomous insight scan]
    insight --> decision{Investigate?}
    decision -->|yes| investigation[Investigation workflow]
    decision -->|no| summary[Insight summary]
    investigation --> summary
    summary --> persist[Persist workflow and workspace state]
    persist --> render[Render workspace views]
```

## SQL Intelligence Lifecycle

```mermaid
flowchart LR
    prompt[Question and context] --> grounding[Schema grounding]
    grounding --> generation[Generate SQL]
    generation --> parser[Parse and normalize SQL]
    parser --> policy[Execution policy]
    policy --> safety[SELECT-only safety checks]
    safety --> explanation[SQL explanation]
    safety --> quality[Result quality checks]
    safety --> recovery[Recovery guidance]
    explanation --> workspace[Workspace UI]
    quality --> workspace
    recovery --> workspace
```

## Persistence Architecture

```mermaid
flowchart TB
    streamlit[Streamlit session state] --> workspaceMemory[Workspace memory]
    fastapi[FastAPI APIs] --> platformRepo[Platform repositories]
    orchestration[Workflow runtime] --> workflowRepo[Workflow repositories]

    platformRepo --> platformDb[(DATABASE_URL)]
    workflowRepo --> workflowDb[(WORKFLOW_DATABASE_URL)]
    workspaceMemory --> platformRepo

    platformDb --> auth[Auth sessions]
    platformDb --> reports[Reports and bookmarks]
    platformDb --> onboarding[Onboarding and preferences]

    workflowDb --> runs[Workflow runs]
    workflowDb --> events[Workflow events]
    workflowDb --> traces[Traces and replay]
    workflowDb --> usage[Telemetry and usage]
```

## Collaboration Workspace Flow

```mermaid
flowchart LR
    user[Authenticated user] --> scope{Workspace scope}
    scope --> personal[Personal workspace]
    scope --> team[Shared team workspace]

    personal --> privateAssets[Private reports, bookmarks, investigations]
    team --> sharedAssets[Shared reports, bookmarks, investigations]

    sharedAssets --> metadata[Owner, creator, visibility, updated-at]
    sharedAssets --> permissions{Can share or edit?}
    permissions -->|admin or analyst| write[Save shared update]
    permissions -->|viewer| read[Read-only shared context]
    write --> activity[Collaboration event]
    read --> history[History workspace]
    activity --> history
    metadata --> history
```

## Telemetry Lifecycle

```mermaid
sequenceDiagram
    participant UI as Streamlit UI
    participant Runtime as Orchestration Runtime
    participant Telemetry as backend.telemetry
    participant Store as Persistence
    participant API as FastAPI Diagnostics

    UI->>Runtime: submit workflow
    Runtime->>Telemetry: emit phase metrics
    Telemetry->>Telemetry: validate schema
    Telemetry->>Store: persist summary/events
    Runtime->>UI: return trace and telemetry
    UI->>UI: render observability panels
    API->>Store: load telemetry
    API->>API: aggregate diagnostics
```

## E2E Testing Flow

```mermaid
flowchart LR
    pytest[pytest tests/e2e] --> fixtures[Playwright fixtures]
    fixtures --> fastapi[Start FastAPI]
    fixtures --> streamlit[Start Streamlit]
    fixtures --> browser[Chromium browser]
    browser --> auth[Login workflow]
    browser --> onboarding[Onboarding workflow]
    browser --> analytics[CSV analytics workflow]
    browser --> exports[Exports and reports]
    browser --> diagnostics[API and connector diagnostics]
    browser --> persistence[Reload and persistence checks]
    fixtures --> artifacts[Screenshots, traces, HTML report]
```
