# Agentic AI Analytics Platform

A production-deployed natural language analytics platform built around agentic workflow patterns: autonomous investigation, guardrails, evaluation, and stateful memory. Implements production-grade controls (query validation, workspace isolation, structured monitoring, cost tracking) suitable for enterprise GenAI deployments.

**Status:** v1 deployed. v2 (multi-agent orchestration via LangGraph, MCP integration, Bedrock backend) under active development.

-----

## Links

- **Live deployment:** https://agentic-ai-analytics-platform.onrender.com
- **Repository:** https://github.com/saikirankonda99/agentic-ai-analytics-platform
- **Author:** [Sai Kiran Konda](https://www.linkedin.com/in/sai-kiran-konda/)

-----

## Overview

Most natural-language-to-SQL implementations terminate at query generation. This platform is designed around the production concerns that begin where generation ends: validation, observability, evaluation, safe execution, and reasoning over results.

The architecture treats SQL generation as one step in a broader analytical workflow. Specialized modules handle semantic grounding, guardrail enforcement, autonomous insight surfacing, multi-step investigation, conversational memory, and per-user workspace isolation. An evaluation harness measures correctness and hallucination rate against a golden set rather than relying on demo-grade qualitative assessment.

The platform is currently deployed on Render with Docker, running against a SQLite demonstration database (Chinook) with CSV upload support for custom datasets.

-----

## Architecture (v1)

```
┌─────────────────────────────────────────────────────┐
│              Streamlit UI                            │
└────────────────────┬─────────────────────────────────┘
                     │
        ┌────────────▼──────────────┐
        │   Workspace + Auth         │   workspace.py
        │   Per-user isolation       │   auth.py
        └────────────┬──────────────┘
                     │
        ┌────────────▼──────────────┐
        │   Semantic Layer           │   semantic.py
        │   Schema-aware context     │
        └────────────┬──────────────┘
                     │
        ┌────────────▼──────────────┐
        │   LLM Abstraction          │   llm.py
        │   Provider-agnostic call   │
        └────────────┬──────────────┘
                     │
        ┌────────────▼──────────────┐
        │   Guardrails               │   guardrails.py
        │   SELECT-only enforcement  │
        │   Destructive op blocking  │
        │   Syntactic validation     │
        └────────────┬──────────────┘
                     │
        ┌────────────▼──────────────┐
        │   Execution                │   db.py
        └────────────┬──────────────┘
                     │
        ┌────────────▼──────────────┐
        │   Autonomous Insights      │   autonomous_insights.py
        │   Anomaly and trend        │
        │   surfacing without        │
        │   explicit prompting       │
        └────────────┬──────────────┘
                     │
        ┌────────────▼──────────────┐
        │   Investigation            │   investigation.py
        │   Follow-up reasoning      │
        │   and multi-step analysis  │
        └────────────┬──────────────┘
                     │
        ┌────────────▼──────────────┐
        │   Memory + Monitoring      │   analytics_memory.py
        │                            │   monitoring.py
        └────────────────────────────┘
```

-----

## Module Responsibilities

|Module                  |Responsibility                                                                             |
|------------------------|-------------------------------------------------------------------------------------------|
|`app.py`                |Streamlit entry point and UI composition                                                   |
|`api.py`                |REST API layer for programmatic access                                                     |
|`workspace.py`          |Per-user workspace and session isolation                                                   |
|`auth.py`               |Authentication and access control                                                          |
|`semantic.py`           |Schema introspection and context construction for LLM grounding                            |
|`llm.py`                |Provider-agnostic LLM interface (OpenAI; designed for Claude/Bedrock extension)            |
|`guardrails.py`         |Query validation: SELECT-only enforcement, destructive operation blocking, syntactic checks|
|`db.py`                 |Database execution layer with connection pooling and error handling                        |
|`autonomous_insights.py`|Proactive pattern detection and anomaly surfacing                                          |
|`investigation.py`      |Multi-step reasoning and follow-up question generation                                     |
|`analytics_memory.py`   |Conversation state and context retention                                                   |
|`monitoring.py`         |Structured logging, latency tracking, cost telemetry                                       |
|`evals/`                |Golden-set evaluation framework                                                            |

-----

## Agentic Design Patterns

The implementation realizes several patterns relevant to production agentic AI systems:

**Tool use with enforced boundaries.** All LLM-generated SQL passes through `guardrails.py` before reaching the database. The validator enforces SELECT-only execution, blocks destructive operations (DROP, DELETE, UPDATE, INSERT, ALTER), and performs syntactic checks. This is the autonomy boundary: the LLM is given a tool, but the tool’s surface area is constrained.

**Autonomous task execution.** `autonomous_insights.py` surfaces patterns, anomalies, and trends without explicit user prompting. The agent decides when surfacing is warranted based on query results and historical context.

**Multi-step investigation reasoning.** `investigation.py` extends single-turn query-response into multi-step analytical sessions. Follow-up questions are generated and reasoned over rather than treating each user input as independent.

**Stateful memory.** `analytics_memory.py` maintains conversation context across turns, enabling references like “filter that by last quarter” without re-stating the prior query.

**Semantic grounding.** `semantic.py` retrieves relevant schema context before generation, reducing hallucination by giving the LLM the actual table and column definitions rather than relying on parametric memory.

**Production observability.** `monitoring.py` captures structured logs, latency metrics, and per-query token cost — the operational telemetry required to debug agentic systems in production.

-----

## Evaluation Framework

The `evals/` module implements a golden-set evaluation harness measuring:

- **Correctness:** does the generated SQL produce the expected result set?
- **Hallucination rate:** queries that compile and execute but compute something different from what was asked
- **Latency:** end-to-end response time
- **Cost per task:** LLM token spend per successful analytical workflow

Hallucination rate is the metric that matters most for production deployment. A SQL query that compiles and returns rows is not the same as a correct answer; the evaluation framework distinguishes the two.

-----

## Tech Stack

|Layer     |Technology                                                 |
|----------|-----------------------------------------------------------|
|Frontend  |Streamlit                                                  |
|Backend   |Python                                                     |
|LLM       |OpenAI API (extensible to Anthropic Claude and AWS Bedrock)|
|Database  |SQLite (Chinook), CSV upload support                       |
|Data Layer|Pandas                                                     |
|Evaluation|Custom golden-set framework                                |
|Deployment|Docker on Render                                           |
|Monitoring|Structured logging, in-app telemetry                       |

-----

## Security and Safety Controls

- **SELECT-only enforcement** at the guardrails layer; destructive operations rejected before execution
- **Syntactic validation** prior to execution; invalid SQL gets a single LLM correction attempt with error context, after which it fails closed
- **Workspace isolation** — uploaded datasets are scoped per user and never shared across sessions
- **Authentication** required for access
- **Audit logging** of every generated query
- **Cost monitoring** with per-request token tracking

-----

## Roadmap (v2)

v2 is a structural upgrade from the current sequential pipeline to a stateful multi-agent graph. The motivation is twofold: enable richer agentic patterns (reflection, planning, multi-agent collaboration) and align the architecture with the orchestration standards used in enterprise agentic AI deployments.

### Target architecture

```
                ┌────────────────────────────┐
                │   User Goal                │
                └─────────────┬──────────────┘
                              │
                      ┌───────▼────────┐
                      │  Planner       │   Decomposes goal into subtasks
                      └───────┬────────┘
                              │
             ┌────────────────┼─────────────────┐
             │                │                  │
      ┌──────▼──────┐  ┌─────▼──────┐  ┌──────▼──────┐
      │ Schema       │  │ History    │  │ Intent      │
      │ (RAG)        │  │ (RAG)      │  │             │
      └──────┬──────┘  └─────┬──────┘  └──────┬──────┘
             │                │                  │
             └────────────────┼──────────────────┘
                              │
                      ┌───────▼────────┐
                      │ SQL Generator  │
                      └───────┬────────┘
                              │
                      ┌───────▼────────┐
                      │ Reflection     │   Critic loop; flags hallucinations
                      └───────┬────────┘
                              │
                      ┌───────▼────────┐
                      │ Human Approval │   For destructive or high-risk operations
                      └───────┬────────┘
                              │
                      ┌───────▼────────┐
                      │ Executor       │
                      └───────┬────────┘
                              │
                      ┌───────▼────────┐
                      │ Summarizer     │
                      └────────────────┘
```

### Planned changes

|Item                                |Rationale                                                                                                                      |
|------------------------------------|-------------------------------------------------------------------------------------------------------------------------------|
|Refactor orchestration to LangGraph |Stateful graph execution replaces sequential pipeline; enables conditional routing, retry loops, and parallel agent execution  |
|Planner agent                       |Decomposes complex multi-step analytical questions into subtasks executed by specialized agents                                |
|Reflection agent                    |Critic loop that validates generated SQL against intent before execution; addresses hallucination as a first-class failure mode|
|History agent                       |Retrieval-augmented context from prior queries to improve generation for recurring analytical patterns                         |
|Human-in-the-loop checkpoint UI     |Explicit approval flow for operations flagged as high-risk or destructive                                                      |
|Expanded golden-set evaluation suite|Target 50+ queries with annotated expected results and hallucination markers                                                   |
|Multi-database adapter              |PostgreSQL, MySQL, and Snowflake support beyond the current SQLite implementation                                              |
|Model Context Protocol (MCP) server |Expose query execution as an MCP-compatible tool consumable by external agentic systems                                        |
|AWS Bedrock backend option          |Claude via Bedrock alongside OpenAI for enterprise deployments requiring AWS-native infrastructure                             |
|Cost monitoring dashboard           |Per-user, per-query token spend visibility                                                                                     |

-----

## Running Locally

```bash
git clone https://github.com/saikirankonda99/agentic-ai-analytics-platform.git
cd agentic-ai-analytics-platform
pip install -r requirements.txt
streamlit run app.py
```

Configure the OpenAI API key via `.streamlit/secrets.toml`:

```toml
OPENAI_API_KEY = "your_api_key_here"
```

Or as an environment variable:

```bash
export OPENAI_API_KEY="your_api_key_here"
```

-----

## Running with Docker

Build:

```bash
docker build -t agentic-ai-analytics-platform .
```

Run:

```bash
docker run --rm -p 8501:8501 \
  -e OPENAI_API_KEY=your_api_key_here \
  agentic-ai-analytics-platform
```

The application is available at `http://localhost:8501`.

To persist telemetry and uploaded data outside the container, mount the data directory:

```bash
docker run --rm -p 8501:8501 \
  -e OPENAI_API_KEY=your_api_key_here \
  -v "$(pwd)/data:/app/data" \
  agentic-ai-analytics-platform
```

The bundled SQLite database in `data/chinook.db` is copied into the image at build time.

-----

## Example Queries

The live deployment runs against the Chinook sample database. Representative queries:

- List all customers
- Top 10 customers by total spending
- Revenue breakdown by country
- Tracks with album and artist
- Genre distribution by region
- Sales performance comparison across markets

CSV upload is supported for analysis against custom datasets within isolated workspaces.

-----

## Contributing

This project is under active development. Contributions, bug reports, and architectural feedback are welcome via GitHub Issues and Pull Requests.

-----

## License

See LICENSE file.

-----

## Author

**Sai Kiran Konda**
[LinkedIn](https://www.linkedin.com/in/sai-kiran-konda/) · [GitHub](https://github.com/saikirankonda99) · saikiran1.konda@gmail.com
