from __future__ import annotations

import time
from typing import Any, TypedDict

from db import get_schema, run_query
from graph.cost_tracker import log_query_cost
from graph.history_store import retrieve_similar_queries, save_query_to_history
from guardrails import is_safe_sql
from llm import DEFAULT_SQL_MODEL, generate_sql_with_telemetry

try:
    from langgraph.graph import END, StateGraph

    LANGGRAPH_AVAILABLE = True
except ImportError:
    END = None
    StateGraph = None
    LANGGRAPH_AVAILABLE = False


MAX_RETRIES = 2


class WorkflowTrace(TypedDict):
    step: str
    status: str
    detail: str


class StepTelemetry(TypedDict):
    step: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: float
    latency_ms: int
    usage_available: bool


class WorkflowState(TypedDict, total=False):
    question: str
    plan: dict[str, Any]
    schema: str
    memory_examples: list[dict[str, str]]
    sql: str
    columns: list[str]
    rows: list[Any]
    error: str | None
    retry_count: int
    last_error: str | None
    last_error_source: str | None
    last_failed_sql: str
    trace: list[WorkflowTrace]
    telemetry: dict[str, Any]


def _new_step_telemetry(
    step: str,
    model: str,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    total_tokens: int = 0,
    cost_usd: float = 0.0,
    latency_ms: int = 0,
    usage_available: bool = False,
) -> StepTelemetry:
    return {
        "step": step,
        "model": model,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "cost_usd": cost_usd,
        "latency_ms": latency_ms,
        "usage_available": usage_available,
    }


def _record_telemetry(state: WorkflowState, step_data: StepTelemetry) -> dict[str, Any]:
    telemetry = dict(state.get("telemetry", {}))
    steps = list(telemetry.get("steps", []))
    steps.append(step_data)

    telemetry.update(
        {
            "steps": steps,
            "prompt_tokens": sum(item.get("prompt_tokens", 0) for item in steps),
            "completion_tokens": sum(item.get("completion_tokens", 0) for item in steps),
            "total_tokens": sum(item.get("total_tokens", 0) for item in steps),
            "cost_usd": sum(item.get("cost_usd", 0.0) for item in steps),
            "latency_ms": sum(item.get("latency_ms", 0) for item in steps),
            "model": next((item.get("model", "") for item in reversed(steps) if item.get("model")), ""),
            "usage_available": any(item.get("usage_available", False) for item in steps),
        }
    )
    return telemetry


def _append_trace(
    state: WorkflowState,
    step: str,
    status: str,
    detail: str,
) -> list[WorkflowTrace]:
    trace = list(state.get("trace", []))
    trace.append({"step": step, "status": status, "detail": detail})
    return trace


def planner_node(state: WorkflowState) -> WorkflowState:
    question = state["question"].strip()
    return {
        "plan": {"intent": question},
        "trace": _append_trace(
            state,
            "planner",
            "success",
            "Question analyzed for SQL planning.",
        ),
    }


def schema_node(state: WorkflowState) -> WorkflowState:
    try:
        schema = get_schema()
        return {
            "schema": schema,
            "trace": _append_trace(
                state,
                "schema retrieval",
                "success",
                "Database schema loaded.",
            ),
        }
    except Exception as exc:
        return {
            "error": f"Schema retrieval failed: {exc}",
            "trace": _append_trace(
                state,
                "schema retrieval",
                "error",
                str(exc),
            ),
        }


def memory_node(state: WorkflowState) -> WorkflowState:
    started = time.perf_counter()
    examples = retrieve_similar_queries(state["question"], top_k=3)
    latency_ms = int((time.perf_counter() - started) * 1000)
    if examples:
        detail = f"Retrieved {len(examples)} similar example(s)."
    else:
        detail = "No similar examples found."

    return {
        "memory_examples": examples,
        "telemetry": _record_telemetry(
            state,
            _new_step_telemetry(
                step="memory retrieval",
                model="chromadb",
                latency_ms=latency_ms,
                usage_available=False,
            ),
        ),
        "trace": _append_trace(
            state,
            "memory retrieval",
            "success",
            detail,
        ),
    }


def _build_generation_prompt(state: WorkflowState) -> str:
    question = state["question"]
    memory_examples = state.get("memory_examples", [])
    memory_block = ""
    if memory_examples:
        formatted_examples = "\n\n".join(
            [
                f"Example question: {item.get('question', '')}\nExample SQL: {item.get('sql', '')}"
                for item in memory_examples
            ]
        )
        memory_block = f"\n\nSimilar successful examples:\n{formatted_examples}"

    if state.get("last_error") and state.get("last_failed_sql"):
        return f"""{question}

Previous SQL failed:
{state['last_failed_sql']}

Database error:
{state['last_error']}

Generate a corrected read-only SQL query.{memory_block}"""
    return f"{question}{memory_block}"


def _build_reflection_prompt(state: WorkflowState) -> str:
    memory_examples = state.get("memory_examples", [])
    memory_block = ""
    if memory_examples:
        formatted_examples = "\n\n".join(
            [
                f"Example question: {item.get('question', '')}\nExample SQL: {item.get('sql', '')}"
                for item in memory_examples
            ]
        )
        memory_block = f"\n\nSimilar successful examples:\n{formatted_examples}"

    return f"""You are fixing a failed SQL query for a SQLite database.

User question:
{state['question']}

Database schema:
{state['schema']}

Failed SQL:
{state.get('last_failed_sql', '')}

Database/runtime error:
{state.get('last_error', '')}

Error source:
{state.get('last_error_source', 'unknown')}

Return ONLY corrected read-only SQL. Do not explain anything.{memory_block}"""


def sql_generation_node(state: WorkflowState) -> WorkflowState:
    if state.get("error") and state.get("retry_count", 0) > MAX_RETRIES:
        return {}

    generation_result = generate_sql_with_telemetry(_build_generation_prompt(state), state["schema"])
    sql = generation_result["sql"].strip()
    step_telemetry = _new_step_telemetry(step="sql generation", **generation_result["telemetry"])
    if not sql or sql.startswith("ERROR:"):
        return {
            "error": sql or "SQL generation failed.",
            "telemetry": _record_telemetry(state, step_telemetry),
            "trace": _append_trace(
                state,
                "sql generation",
                "error",
                sql or "No SQL returned.",
            ),
        }

    return {
        "sql": sql,
        "error": None,
        "last_error_source": None,
        "telemetry": _record_telemetry(state, step_telemetry),
        "trace": _append_trace(
            state,
            "sql generation",
            "success",
            f"Generated SQL attempt {state.get('retry_count', 0) + 1}.",
        ),
    }


def validation_node(state: WorkflowState) -> WorkflowState:
    sql = state.get("sql", "").strip()
    if not sql:
        error = "No SQL was generated."
        return {
            "error": error,
            "last_error": error,
            "last_error_source": "validation",
            "last_failed_sql": "",
            "trace": _append_trace(state, "validation", "error", error),
        }

    if not is_safe_sql(sql):
        error = "Unsafe query blocked. Only read-only SELECT queries are allowed."
        return {
            "error": error,
            "last_error": error,
            "last_error_source": "validation",
            "last_failed_sql": sql,
            "trace": _append_trace(state, "validation", "error", error),
        }

    return {
        "error": None,
        "last_error_source": None,
        "trace": _append_trace(
            state,
            "validation",
            "success",
            "SQL passed safety validation.",
        ),
    }


def reflection_node(state: WorkflowState) -> WorkflowState:
    retry_count = state.get("retry_count", 0) + 1
    reflection_result = generate_sql_with_telemetry(_build_reflection_prompt(state), state["schema"])
    corrected_sql = reflection_result["sql"].strip()
    step_telemetry = _new_step_telemetry(step="reflection", **reflection_result["telemetry"])

    if not corrected_sql or corrected_sql.startswith("ERROR:"):
        error = corrected_sql or "Reflection failed to generate corrected SQL."
        return {
            "retry_count": retry_count,
            "error": error,
            "telemetry": _record_telemetry(state, step_telemetry),
            "trace": _append_trace(
                state,
                "reflection",
                "error",
                f"Correction attempt {retry_count}/{MAX_RETRIES} failed: {error}",
            ),
        }

    return {
        "retry_count": retry_count,
        "sql": corrected_sql,
        "error": None,
        "telemetry": _record_telemetry(state, step_telemetry),
        "trace": _append_trace(
            state,
            "reflection",
            "retry",
            f"Correction attempt {retry_count}/{MAX_RETRIES} generated updated SQL.",
        ),
    }


def execution_node(state: WorkflowState) -> WorkflowState:
    started = time.perf_counter()
    try:
        columns, rows = run_query(state["sql"])
        latency_ms = int((time.perf_counter() - started) * 1000)
        save_query_to_history(
            question=state["question"],
            sql=state["sql"],
            success=True,
        )
        telemetry = _record_telemetry(
            state,
            _new_step_telemetry(
                step="execution",
                model="sqlite",
                latency_ms=latency_ms,
                usage_available=False,
            ),
        )
        log_query_cost(
            question=state["question"],
            model=telemetry.get("model") or DEFAULT_SQL_MODEL,
            cost_usd=telemetry.get("cost_usd", 0.0),
            tokens=telemetry.get("total_tokens", 0),
            latency_ms=telemetry.get("latency_ms", 0),
        )
        return {
            "columns": columns,
            "rows": rows,
            "error": None,
            "last_error": None,
            "last_error_source": None,
            "telemetry": telemetry,
            "trace": _append_trace(
                state,
                "execution",
                "success",
                f"Query executed successfully with {len(rows)} rows.",
            ),
        }
    except Exception as exc:
        latency_ms = int((time.perf_counter() - started) * 1000)
        error = f"SQL execution failed: {exc}"
        return {
            "columns": [],
            "rows": [],
            "error": error,
            "last_error": str(exc),
            "last_error_source": "execution",
            "last_failed_sql": state.get("sql", ""),
            "telemetry": _record_telemetry(
                state,
                _new_step_telemetry(
                    step="execution",
                    model="sqlite",
                    latency_ms=latency_ms,
                    usage_available=False,
                ),
            ),
            "trace": _append_trace(state, "execution", "error", error),
        }


def _route_after_validation(state: WorkflowState) -> str:
    if state.get("error"):
        if state.get("retry_count", 0) < MAX_RETRIES:
            return "reflection"
        return "end"
    return "execution"


def _route_after_execution(state: WorkflowState) -> str:
    if state.get("error") and state.get("retry_count", 0) < MAX_RETRIES:
        return "reflection"
    return "end"


def build_workflow():
    if not LANGGRAPH_AVAILABLE:
        return None

    graph = StateGraph(WorkflowState)
    graph.add_node("planner", planner_node)
    graph.add_node("schema", schema_node)
    graph.add_node("memory", memory_node)
    graph.add_node("sql_generation", sql_generation_node)
    graph.add_node("validation", validation_node)
    graph.add_node("reflection", reflection_node)
    graph.add_node("execution", execution_node)

    graph.set_entry_point("planner")
    graph.add_edge("planner", "schema")
    graph.add_edge("schema", "memory")
    graph.add_edge("memory", "sql_generation")
    graph.add_edge("sql_generation", "validation")
    graph.add_conditional_edges(
        "validation",
        _route_after_validation,
        {
            "reflection": "reflection",
            "execution": "execution",
            "end": END,
        },
    )
    graph.add_conditional_edges(
        "execution",
        _route_after_execution,
        {
            "reflection": "reflection",
            "end": END,
        },
    )
    graph.add_edge("reflection", "validation")

    return graph.compile()


workflow = build_workflow()


def _run_linear(question: str) -> WorkflowState:
    state: WorkflowState = {
        "question": question,
        "error": None,
        "retry_count": 0,
        "last_error": None,
        "last_error_source": None,
        "last_failed_sql": "",
        "telemetry": {
            "steps": [],
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "cost_usd": 0.0,
            "latency_ms": 0,
            "model": "",
            "usage_available": False,
        },
        "trace": [],
    }

    state.update(planner_node(state))
    if state.get("error"):
        return state

    state.update(schema_node(state))
    if state.get("error"):
        return state

    state.update(memory_node(state))
    if state.get("error"):
        return state

    while True:
        state.update(sql_generation_node(state))
        if state.get("error"):
            return state

        state.update(validation_node(state))
        if state.get("error"):
            if state.get("retry_count", 0) < MAX_RETRIES:
                state.update(reflection_node(state))
                if state.get("error"):
                    return state
                continue
            return state

        state.update(execution_node(state))
        if state.get("error") and state.get("retry_count", 0) < MAX_RETRIES:
            state.update(reflection_node(state))
            if state.get("error"):
                return state
            continue
        return state


def run_workflow(question: str) -> WorkflowState:
    initial_state: WorkflowState = {
        "question": question,
        "error": None,
        "retry_count": 0,
        "last_error": None,
        "last_error_source": None,
        "last_failed_sql": "",
        "memory_examples": [],
        "telemetry": {
            "steps": [],
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "cost_usd": 0.0,
            "latency_ms": 0,
            "model": "",
            "usage_available": False,
        },
        "trace": [],
    }

    if workflow is None:
        return _run_linear(question)

    result = workflow.invoke(initial_state)
    return WorkflowState(result)
