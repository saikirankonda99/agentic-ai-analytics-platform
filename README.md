# Agentic AI Analytics Platform

Production-oriented natural language analytics system designed around agentic workflow patterns, safe SQL generation, evaluation, observability, and multi-step analytical reasoning.

The platform extends beyond text-to-SQL generation into the operational concerns required for deploying LLM-driven analytics systems in realistic environments: validation, hallucination mitigation, telemetry, workspace isolation, evaluation, and conversational analytical workflows.

Current deployment supports SQLite and CSV-backed datasets with isolated user workspaces. The architecture is intentionally modular to support future migration toward distributed multi-agent orchestration.

---

# Live System

- Live Deployment: https://agentic-ai-analytics-platform.onrender.com
- Repository: https://github.com/saikirankonda99/agentic-ai-analytics-platform
- Author: Sai Kiran Konda

---

# Why This Project Exists

Most NL-to-SQL demos stop at query generation. Real systems fail after generation:

- queries hallucinate valid-looking but incorrect logic
- generated SQL becomes unsafe
- analytical context disappears between turns
- no observability exists for debugging failures
- no evaluation framework measures correctness
- no isolation exists between users or datasets

This project was built to explore the engineering problems that emerge when LLM-based analytics systems move from demos into production-style workflows.

The architecture treats SQL generation as one component inside a broader analytical system that includes:

- semantic grounding
- query guardrails
- autonomous insight surfacing
- conversational memory
- multi-step investigations
- evaluation harnesses
- telemetry and cost monitoring

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

## Why Provider Abstraction

`llm.py` isolates model providers from orchestration logic.

This prevents tight coupling to a single vendor and allows future migration toward:
- OpenAI
- Claude
- Bedrock-hosted models
- local inference endpoints

without rewriting analytical workflows.

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

Some recurring engineering problems during implementation:

- controlling hallucinated joins
- reducing invalid aggregation generation
- handling malformed SQL correction loops
- maintaining conversational context consistency
- preventing schema drift during CSV uploads
- balancing latency against deeper reasoning chains
- keeping prompts deterministic across workflows

These issues significantly influenced the architecture.

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
