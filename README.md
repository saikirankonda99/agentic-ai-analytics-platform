# Agentic AI Analytics Platform

Production-oriented natural language analytics system designed around agentic workflow patterns, safe SQL generation, evaluation, observability, and multi-step analytical reasoning.

The platform extends beyond text-to-SQL generation into the operational concerns required for deploying LLM-driven analytics systems in realistic environments: validation, hallucination mitigation, telemetry, workspace isolation, evaluation, and conversational analytical workflows.

Current deployment supports SQLite and CSV-backed datasets with isolated user workspaces. The architecture is intentionally modular to support future migration toward distributed multi-agent orchestration.

For the production architecture, orchestration lifecycle, telemetry flow, investigation system, deployment model, environment setup, troubleshooting posture, screenshots plan, and technical decisions, see [Enterprise Platform Overview](docs/enterprise-platform-overview.md).

---

# Live System

- Live Deployment: https://agentic-ai-analytics-platform.onrender.com
- Repository: https://github.com/saikirankonda99/agentic-ai-analytics-platform
- Author: Sai Kiran Konda

---

# Why I Built This

I started this project after noticing that most text-to-SQL demos work for about 30 seconds before things start breaking.

Simple prompts were usually fine:
- "top customers by revenue"
- "sales by country"
- "monthly revenue trends"

The problems started once queries became conversational.

Users would ask things like:
> "Now compare that against last quarter"

or

> "Only show the top regions from the previous result"

and the system would completely lose context or generate SQL that technically executed but answered the wrong question.

One of the more frustrating issues early on was GPT generating joins against columns that sounded reasonable but didn’t actually exist in the schema. In a few cases the SQL compiled successfully and returned believable-looking results, which was worse than failing outright because the mistake was harder to notice.

At that point the project became less about prompt engineering and more about:
- validation
- debugging visibility
- conversational state
- evaluation
- execution safety

A surprising amount of the work ended up going into handling failure cases rather than improving generation quality itself.

---

# Core Design Goals

## 1. Fail Closed Instead of Failing Open

Unsafe or malformed SQL should never reach execution.

The system validates all generated SQL before execution using:
- SELECT-only enforcement
- destructive operation blocking
- syntactic validation
- retry-with-context correction flow

If correction fails, execution stops.

---

## 2. Reduce Hallucination Risk

LLMs frequently generate syntactically correct but semantically incorrect SQL.

The system reduces hallucinations through:
- schema-aware grounding
- semantic context retrieval
- evaluation harnesses
- reflection-oriented investigation flows
- conversational context retention

---

## 3. Preserve Analytical Context

Real analytical workflows are iterative.

The platform maintains conversational memory to support follow-up reasoning such as:

> "Filter that to last quarter"

or

> "Compare this against the previous region"

without regenerating context from scratch.

---

## 4. Prioritize Operational Visibility

Production AI systems require telemetry.

The platform tracks:
- request latency
- token usage
- query execution history
- failure traces
- generated SQL audit logs

This observability layer exists to make debugging and evaluation possible.

---

# Current Architecture (v1)

```text
┌─────────────────────────────────────────────────────┐
│                  Streamlit UI                       │
└────────────────────┬────────────────────────────────┘
                     │
        ┌────────────▼──────────────┐
        │ Workspace + Auth           │
        │ Per-user isolation         │
        └────────────┬──────────────┘
                     │
        ┌────────────▼──────────────┐
        │ Semantic Grounding Layer   │
        │ Schema-aware retrieval     │
        └────────────┬──────────────┘
                     │
        ┌────────────▼──────────────┐
        │ LLM Abstraction Layer      │
        │ Provider-agnostic calls    │
        └────────────┬──────────────┘
                     │
        ┌────────────▼──────────────┐
        │ Guardrails                 │
        │ SQL validation             │
        │ Destructive op blocking    │
        └────────────┬──────────────┘
                     │
        ┌────────────▼──────────────┐
        │ Query Execution Layer      │
        └────────────┬──────────────┘
                     │
        ┌────────────▼──────────────┐
        │ Autonomous Insights        │
        │ Trend + anomaly surfacing  │
        └────────────┬──────────────┘
                     │
        ┌────────────▼──────────────┐
        │ Investigation Engine       │
        │ Multi-step reasoning       │
        └────────────┬──────────────┘
                     │
        ┌────────────▼──────────────┐
        │ Memory + Monitoring        │
        └────────────────────────────┘
```

---

# Production Workspace Evolution

The current workspace is organized as an AI analytics operations console rather than a single chat demo.

Primary sections:
- `Overview`: natural-language analytics execution, charts, SQL inspection, and insight summaries
- `Operations`: AI operations center with runtime health, workflow queue visibility, agent utilization, trends, and recommendations
- `Copilot`: conversation history, workflow timeline, and model telemetry
- `Investigations`: autonomous drill-down sessions, persisted investigation memory, and recommendation follow-ups
- `Monitoring`: scheduled KPI checks, executive briefing state, and monitoring run history
- `Agents`: active agent panels, reasoning snapshots, latency breakdowns, and telemetry exports
- `API`: runtime diagnostics, endpoint map, OpenAI posture, and exportable observability payloads
- `History`: recent workflow runs and generated SQL

Operational improvements:
- workflow correlation IDs across UI, telemetry, and logs
- centralized telemetry schema in `backend.telemetry`
- coordinator execution graph with agent dependencies, transition timestamps, confidence, and recovery state
- execution policy diagnostics with retry, confidence, degradation, and escalation decisions
- persisted workspace sessions with replayable transcripts
- OpenAI request diagnostics with exception chains and retry metadata
- JSON/CSV telemetry export for support and debugging
- FastAPI `/diagnostics` endpoint for runtime posture
- workflow inspection endpoints for telemetry, replay, and investigation retrieval
- workspace inspection endpoints for session transcripts, saved SQL history, and report exports
- operations endpoints for telemetry event filtering and control-plane summaries

Detailed control-plane notes are available in [docs/platform-control-plane.md](docs/platform-control-plane.md).

Recommended local validation:

```bash
python -m ruff check
python -m pytest
python -m streamlit run app.py --server.port 8501 --server.headless true
```

---

# Repository Structure

```text
agentic-ai-analytics-platform/

├── app.py
├── api.py
├── auth.py
├── workspace.py
├── semantic.py
├── llm.py
├── guardrails.py
├── db.py
├── autonomous_insights.py
├── investigation.py
├── analytics_memory.py
├── monitoring.py
├── requirements.txt
├── Dockerfile
├── data/
├── evals/
└── tests/
```

---

# Engineering Decisions

## Why Streamlit

Streamlit allowed rapid iteration on conversational analytics workflows while keeping the focus on backend orchestration and analytical behavior rather than frontend engineering overhead.

---

## Why SQLite Initially

SQLite reduced infrastructure complexity during early iteration and enabled rapid experimentation with:
- query validation
- semantic grounding
- evaluation logic
- memory handling

The architecture intentionally abstracts execution logic to support PostgreSQL, Snowflake, and MySQL migration later.

---

## Why Provider Abstraction Exists

I originally wired the project directly to the OpenAI SDK and quickly regretted it once the orchestration logic started growing.

Prompt formatting, retries, response parsing, token accounting, and provider-specific quirks were leaking into unrelated parts of the codebase. I hit a similar problem on an earlier Claude experiment where changing SDK versions forced changes across multiple files.

`llm.py` exists mainly to keep provider-specific logic isolated.

Right now the implementation still primarily targets OpenAI, but the abstraction layer makes it easier to experiment with:
- Claude via Bedrock
- local inference endpoints
- fallback provider routing
- provider-specific retry behavior

without rewriting investigation or execution workflows.

---

## Why Guardrails Exist Outside the Prompt

Prompt-only safety is insufficient.

Validation occurs programmatically before execution because:
- prompts can drift
- models hallucinate
- jailbreaks happen
- unsafe SQL must fail deterministically

---

## Why Stateful Memory Matters

Most text-to-SQL systems treat every query independently.

Analytical workflows are iterative by nature, so the platform preserves:
- prior filters
- previous aggregations
- user investigation history
- contextual references

across turns.

---

# Module Responsibilities

| Module | Responsibility |
|---|---|
| `app.py` | Streamlit UI entrypoint |
| `api.py` | REST API layer |
| `workspace.py` | Per-user workspace isolation |
| `auth.py` | Authentication and session management |
| `semantic.py` | Schema introspection and semantic grounding |
| `llm.py` | Provider abstraction layer |
| `guardrails.py` | SQL safety enforcement |
| `db.py` | Query execution and database access |
| `autonomous_insights.py` | Trend and anomaly surfacing |
| `investigation.py` | Follow-up reasoning workflows |
| `analytics_memory.py` | Stateful conversational memory |
| `monitoring.py` | Logging, telemetry, latency tracking |
| `evals/` | Golden-set evaluation framework |
| `tests/` | Validation and regression testing |

---

# Agentic Workflow Patterns

## Controlled Tool Use

The LLM does not receive unrestricted database access.

All generated SQL passes through:
- syntactic validation
- restricted operation checks
- execution policy enforcement

before execution.

This defines the autonomy boundary.

---

## Autonomous Insight Generation

The system proactively surfaces:
- anomalies
- trends
- outliers
- unexpected distributions

without requiring explicit user prompting.

---

## Multi-Step Investigations

Analytical sessions are modeled as iterative workflows rather than isolated prompts.

The system can:
- generate follow-up questions
- refine prior analysis
- compare historical queries
- continue investigations across turns

---

## Stateful Context Retention

Conversation memory enables references to:
- prior aggregations
- earlier filters
- previous datasets
- historical analytical context

without regenerating the entire workflow.

---

# Evaluation Framework

The `evals/` module implements a golden-set evaluation harness focused on production failure modes.

Measured metrics include:

| Metric | Purpose |
|---|---|
| Correctness | Does SQL produce the intended result? |
| Hallucination Rate | Did the query return plausible but incorrect answers? |
| Latency | End-to-end workflow execution time |
| Token Cost | LLM usage cost per analytical task |

The evaluation layer exists because successful execution does not imply correctness.

A query that compiles and returns rows may still produce analytically invalid output.

---

# Observability and Monitoring

Production AI systems require debugging visibility.

The monitoring layer captures:
- structured logs
- generated SQL audit history
- token consumption
- latency metrics
- execution failures
- correction attempts

This telemetry is used to identify:
- hallucination patterns
- slow workflows
- repeated correction failures
- prompt regressions

---

# Security Controls

## SQL Safety Enforcement

The platform blocks:
- DROP
- DELETE
- UPDATE
- INSERT
- ALTER
- TRUNCATE

before execution.

Only validated SELECT queries are allowed.

---

## Workspace Isolation

Uploaded datasets remain isolated per user workspace and are never shared across sessions.

---

## Audit Logging

Every generated query is logged for:
- traceability
- debugging
- evaluation
- failure analysis

---

# Performance Notes

Current deployment targets correctness and workflow reliability over raw throughput.

Observed characteristics:
- average response latency: 3–8 seconds
- lower latency for schema-aware repeated queries
- higher latency during multi-step investigation flows
- token cost increases during iterative reasoning

Optimization work is ongoing.

---

# Known Limitations

The current system still has several limitations:

- SQLite backend is not suitable for high concurrency
- conversational memory is session-scoped only
- autonomous insight generation can over-surface weak trends
- long-context prompts increase token cost significantly
- evaluation coverage is still limited relative to production-scale datasets

These limitations are intentionally documented because operational weaknesses matter in real deployments.

---

# Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Streamlit |
| Backend | Python |
| Data Layer | Pandas |
| Database | SQLite |
| LLM Provider | OpenAI |
| Containerization | Docker |
| Deployment | Render |
| Evaluation | Custom golden-set framework |
| Monitoring | Structured logging + telemetry |

---

# Running Locally

## Clone Repository

```bash
git clone https://github.com/saikirankonda99/agentic-ai-analytics-platform.git

cd agentic-ai-analytics-platform
```

---

## Install Dependencies

```bash
pip install -r requirements.txt
```

---

## Configure API Key

### Option 1 — Environment Variable

```bash
export OPENAI_API_KEY="your_api_key_here"
```

### Option 2 — Streamlit Secrets

Create:

```text
.streamlit/secrets.toml
```

Add:

```toml
OPENAI_API_KEY="your_api_key_here"
```

---

## Start Application

```bash
streamlit run app.py
```

---

# Docker Deployment

## Build

```bash
docker build -t agentic-ai-analytics-platform .
```

---

## Run

```bash
docker run --rm -p 8501:8501 \
-e OPENAI_API_KEY=your_api_key_here \
agentic-ai-analytics-platform
```

---

# Example Analytical Queries

Example prompts against the Chinook dataset:

- Top customers by revenue
- Revenue by geography
- Artist performance comparison
- Genre distribution trends
- Regional sales breakdown
- Monthly purchasing behavior
- Album sales by market segment

CSV uploads are also supported for isolated custom dataset analysis.

---

# Challenges Encountered During Development

Some of the harder problems were not the ones I expected going into the project.

One recurring issue was hallucinated columns. GPT would generate things like `customer_revenue` or `regional_sales_total` even when those columns didn’t exist. Schema grounding reduced this quite a bit, but it still showed up occasionally when prompts became long or conversational context drifted.

Another annoying issue was malformed correction loops. Sometimes the retry flow would bounce between two different invalid SQL queries indefinitely because each correction introduced a new syntax problem. Retry limits and stricter validation logic were added after that started showing up repeatedly during testing.

CSV uploads also introduced problems I didn’t initially think about. If a user uploaded a new dataset mid-session, conversational memory could reference tables or columns from the previous schema. That forced me to add memory invalidation logic tied to workspace state.

Token growth became another issue once investigation chains got longer. Earlier versions kept appending too much historical context into prompts, which increased latency and cost pretty quickly.

There are still cases where:
- aggregation logic becomes overly complex
- anomaly detection over-surfaces weak trends
- long conversational chains drift semantically over time

Those are still being worked on.

---

# Roadmap (v2)

The next iteration transitions from a sequential pipeline toward stateful multi-agent orchestration.

Primary goals:
- richer analytical reasoning
- reflection loops
- parallel agent execution
- planner-based decomposition
- enterprise orchestration compatibility

---

## Planned Improvements

| Planned Work | Motivation |
|---|---|
| LangGraph orchestration | Stateful graph execution |
| Reflection agent | Hallucination detection before execution |
| Planner agent | Multi-step task decomposition |
| History-aware retrieval | Better analytical continuity |
| Snowflake/Postgres adapters | Production database support |
| MCP server support | External agent interoperability |
| Bedrock integration | Enterprise AWS-native deployments |
| Expanded evaluation suite | Larger correctness benchmark coverage |
| Human approval checkpoints | High-risk operation review |
| Telemetry dashboard | Per-user cost visibility |

---

# Contributing

The project is still evolving and architectural feedback is welcome.

Contributions are encouraged for:
- orchestration improvements
- evaluation methodology
- hallucination mitigation
- database adapters
- telemetry and monitoring
- testing coverage

---

# License

See LICENSE file.

---

# Author

Sai Kiran Konda

- LinkedIn: https://www.linkedin.com/in/sai-kiran-konda/
- GitHub: https://github.com/saikirankonda99
- Email: saikiran1.konda@gmail.com
