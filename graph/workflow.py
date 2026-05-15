"""
LangGraph multi-agent workflow for GenAI SQL Assistant — Agentic Edition.

Agents:
  planner        → decomposes the user query into a structured plan
  schema_agent   → RAG retrieval over schema (wraps your existing rag.py)
  history_agent  → retrieves similar past queries from vector store
  sql_generator  → drafts SQL from plan + schema context
  reflection     → LLM critic: validates SQL vs intent, checks safety
  executor       → runs the query (wraps your existing executor.py)
  summarizer     → plain-English insight (wraps your existing insight_generator.py)

Human-in-the-loop checkpoint fires when reflection marks a query as DESTRUCTIVE
or when confidence is below the threshold.
"""

from __future__ import annotations

import json
from typing import Annotated, Any, Literal

from langchain_core.messages import AIMessage, HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

# ── reuse existing modules ────────────────────────────────────────────────────
from app.rag import retrieve_schema_context
from app.sql_generator import generate_sql
from app.sql_validator import validate_sql
from app.executor import execute_query
from app.insight_generator import generate_insight
from graph.history_store import retrieve_similar_queries, save_query_to_history
from graph.cost_tracker import log_query_cost

# ── shared state ──────────────────────────────────────────────────────────────

class AgentState(TypedDict):
    # conversation
    messages: Annotated[list, add_messages]
    user_question: str

    # planner output
    plan: dict                    # {intent, tables_needed, filters, aggregations, complexity}

    # context gathered by agents
    schema_context: str
    history_context: str

    # sql lifecycle
    sql_draft: str
    sql_final: str
    reflection: dict              # {valid, safe, matches_intent, issues, confidence}
    validation_result: dict       # from your existing sql_validator

    # execution
    query_result: Any             # DataFrame or error string
    insight: str

    # control
    iteration: int                # reflection retry counter (max 2)
    awaiting_human: bool          # True when human approval needed
    human_approved: bool
    error: str | None

    # telemetry
    cost_usd: float
    tokens_used: int


# ── LLM ──────────────────────────────────────────────────────────────────────

def _get_llm(model: str = "gpt-4o", temperature: float = 0) -> ChatOpenAI:
    return ChatOpenAI(model=model, temperature=temperature)


# ── Agent nodes ───────────────────────────────────────────────────────────────

def planner_node(state: AgentState) -> dict:
    """Decomposes the user question into a structured query plan."""
    llm = _get_llm()
    prompt = f"""You are a data analyst planning how to answer a business question with SQL.

User question: {state["user_question"]}

Respond ONLY with a JSON object (no markdown fences) with these keys:
- intent: one-sentence description of what the user wants
- tables_needed: list of likely table names
- filters: list of filter conditions in plain English
- aggregations: list of aggregations (e.g. "SUM of revenue", "COUNT of orders")
- complexity: one of [simple, moderate, complex]
- needs_clarification: true if the question is ambiguous
- clarification_question: (only if needs_clarification is true) what to ask the user
"""
    response = llm.invoke([HumanMessage(content=prompt)])
    try:
        plan = json.loads(response.content)
    except json.JSONDecodeError:
        # fallback: extract JSON from response
        import re
        match = re.search(r"\{.*\}", response.content, re.DOTALL)
        plan = json.loads(match.group()) if match else {
            "intent": state["user_question"],
            "tables_needed": [],
            "filters": [],
            "aggregations": [],
            "complexity": "moderate",
            "needs_clarification": False,
        }

    return {
        "plan": plan,
        "messages": [AIMessage(content=f"📋 Plan: {plan.get('intent', 'Analyzing query...')}")],
    }


def schema_agent_node(state: AgentState) -> dict:
    """RAG retrieval over schema — wraps your existing rag.py."""
    tables_hint = " ".join(state["plan"].get("tables_needed", []))
    query = f"{state['user_question']} {tables_hint}".strip()
    schema_context = retrieve_schema_context(query)
    return {"schema_context": schema_context}


def history_agent_node(state: AgentState) -> dict:
    """Retrieves semantically similar past queries for few-shot context."""
    similar = retrieve_similar_queries(state["user_question"], top_k=3)
    history_context = "\n".join(
        f"Q: {item['question']}\nSQL: {item['sql']}" for item in similar
    ) if similar else "No similar past queries found."
    return {"history_context": history_context}


def sql_generator_node(state: AgentState) -> dict:
    """Generates SQL using plan + schema + history context."""
    sql = generate_sql(
        question=state["user_question"],
        schema_context=state["schema_context"],
        history_context=state["history_context"],
        plan=state["plan"],
    )
    return {
        "sql_draft": sql,
        "messages": [AIMessage(content=f"🔨 Generated SQL draft (iteration {state['iteration'] + 1})")],
    }


def reflection_node(state: AgentState) -> dict:
    """LLM critic that checks SQL correctness, safety, and intent alignment."""
    llm = _get_llm(temperature=0)
    prompt = f"""You are a senior SQL reviewer. Evaluate this SQL query.

User intent: {state['plan'].get('intent', state['user_question'])}
Schema context:
{state['schema_context']}

SQL to review:
{state['sql_draft']}

Respond ONLY with a JSON object (no markdown fences):
- valid: true/false (is the SQL syntactically and semantically correct?)
- safe: true/false (is it read-only? No DROP/DELETE/UPDATE/INSERT?)
- matches_intent: true/false (does it answer what the user asked?)
- destructive: true/false (does it modify data or schema?)
- confidence: 0.0 to 1.0
- issues: list of specific problems found (empty list if none)
- fixed_sql: if valid is false OR matches_intent is false, provide corrected SQL; otherwise null
"""
    response = llm.invoke([HumanMessage(content=prompt)])
    try:
        reflection = json.loads(response.content)
    except json.JSONDecodeError:
        import re
        match = re.search(r"\{.*\}", response.content, re.DOTALL)
        reflection = json.loads(match.group()) if match else {
            "valid": False, "safe": True, "matches_intent": False,
            "destructive": False, "confidence": 0.0,
            "issues": ["Could not parse reflection"], "fixed_sql": None,
        }

    # apply fixed SQL if critic provided one
    sql_final = reflection.get("fixed_sql") or state["sql_draft"]

    issues_str = "; ".join(reflection.get("issues", [])) or "None"
    return {
        "reflection": reflection,
        "sql_final": sql_final,
        "awaiting_human": reflection.get("destructive", False),
        "messages": [AIMessage(
            content=f"🔍 Reflection — confidence: {reflection.get('confidence', 0):.0%} | issues: {issues_str}"
        )],
    }


def human_approval_node(state: AgentState) -> dict:
    """
    Pause point: Streamlit UI reads awaiting_human=True and renders an approval widget.
    When the user approves/rejects, the UI resumes the graph with human_approved set.
    This node is a no-op in the graph itself — it's the interrupt mechanism.
    """
    # LangGraph will interrupt here when using .stream() with interrupt_before=["human_approval"]
    return {}


def executor_node(state: AgentState) -> dict:
    """Executes the final SQL — wraps your existing executor.py."""
    # safety re-check before execution
    validation = validate_sql(state["sql_final"])
    if not validation["is_valid"]:
        return {
            "error": f"Validator blocked execution: {validation['error']}",
            "query_result": None,
            "validation_result": validation,
        }

    result_df, cost_info = execute_query(state["sql_final"])

    # persist to history store for future retrieval
    save_query_to_history(
        question=state["user_question"],
        sql=state["sql_final"],
        success=result_df is not None,
    )

    # cost tracking
    log_query_cost(
        question=state["user_question"],
        model="gpt-4o",
        cost_usd=cost_info.get("cost_usd", 0.0),
        tokens=cost_info.get("tokens", 0),
    )

    return {
        "query_result": result_df,
        "cost_usd": cost_info.get("cost_usd", 0.0),
        "tokens_used": cost_info.get("tokens", 0),
        "validation_result": validation,
        "error": None,
    }


def summarizer_node(state: AgentState) -> dict:
    """Generates plain-English insight — wraps your existing insight_generator.py."""
    if state.get("error"):
        insight = f"❌ Query failed: {state['error']}"
    elif state["query_result"] is None:
        insight = "No results returned."
    else:
        insight = generate_insight(
            question=state["user_question"],
            sql=state["sql_final"],
            result_df=state["query_result"],
        )
    return {
        "insight": insight,
        "messages": [AIMessage(content=insight)],
    }


# ── Routing logic ─────────────────────────────────────────────────────────────

def should_retry_or_proceed(state: AgentState) -> Literal["retry", "human_approval", "executor"]:
    """After reflection: retry generation, request human approval, or execute."""
    reflection = state.get("reflection", {})
    iteration = state.get("iteration", 0)

    if reflection.get("destructive"):
        return "human_approval"

    all_good = (
        reflection.get("valid", False)
        and reflection.get("safe", False)
        and reflection.get("matches_intent", False)
        and reflection.get("confidence", 0) >= 0.75
    )

    if all_good or iteration >= 2:
        return "executor"

    return "retry"


def after_human_approval(state: AgentState) -> Literal["executor", "end"]:
    """Route based on human decision."""
    return "executor" if state.get("human_approved") else "end"


# ── Build the graph ───────────────────────────────────────────────────────────

def build_workflow() -> StateGraph:
    graph = StateGraph(AgentState)

    # add nodes
    graph.add_node("planner", planner_node)
    graph.add_node("schema_agent", schema_agent_node)
    graph.add_node("history_agent", history_agent_node)
    graph.add_node("sql_generator", sql_generator_node)
    graph.add_node("reflection", reflection_node)
    graph.add_node("human_approval", human_approval_node)
    graph.add_node("executor", executor_node)
    graph.add_node("summarizer", summarizer_node)

    # edges
    graph.set_entry_point("planner")
    graph.add_edge("planner", "schema_agent")
    graph.add_edge("schema_agent", "history_agent")
    graph.add_edge("history_agent", "sql_generator")
    graph.add_edge("sql_generator", "reflection")

    graph.add_conditional_edges(
        "reflection",
        should_retry_or_proceed,
        {
            "retry": "sql_generator",      # loop back, increment iteration
            "human_approval": "human_approval",
            "executor": "executor",
        },
    )

    graph.add_conditional_edges(
        "human_approval",
        after_human_approval,
        {"executor": "executor", "end": END},
    )

    graph.add_edge("executor", "summarizer")
    graph.add_edge("summarizer", END)

    return graph.compile(interrupt_before=["human_approval"])


# module-level compiled graph
workflow = build_workflow()
