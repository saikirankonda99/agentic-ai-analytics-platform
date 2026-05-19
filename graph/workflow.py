from __future__ import annotations

import time
from datetime import datetime
from typing import Any, Callable, TypedDict

from analytics_memory import contextualize_followup, memory_prompt_block
from db import get_schema, run_query
from graph.cost_tracker import log_query_cost
from graph.history_store import retrieve_similar_queries, save_query_to_history
from guardrails import is_safe_sql
from llm import DEFAULT_SQL_MODEL, generate_sql_with_telemetry, stream_sql_with_telemetry
from workspace import workspace_prompt_block

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
    timestamp: str
    phase: str


class StepTelemetry(TypedDict, total=False):
    step: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: float
    latency_ms: int
    usage_available: bool
    error_type: str
    error_message: str
    error_attempt: int
    error_max_attempts: int
    error_details: dict[str, Any]


class WorkflowState(TypedDict, total=False):
    question: str
    plan: dict[str, Any]
    schema: str
    memory_examples: list[dict[str, str]]
    sql: str
    columns: list[str]
    rows: list[Any]
    semantic_context: dict[str, Any]
    conversation_context: dict[str, Any]
    workspace_context: dict[str, Any]
    effective_question: str
    followup_context: dict[str, Any]
    error: str | None
    retry_count: int
    last_error: str | None
    last_error_source: str | None
    last_failed_sql: str
    trace: list[WorkflowTrace]
    telemetry: dict[str, Any]
    event: dict[str, Any]


WorkflowEventCallback = Callable[[str, WorkflowState, str, str], None]


def _new_step_telemetry(
    step: str,
    model: str,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    total_tokens: int = 0,
    cost_usd: float = 0.0,
    latency_ms: int = 0,
    usage_available: bool = False,
    **extra: Any,
) -> StepTelemetry:
    telemetry: StepTelemetry = {
        "step": step,
        "model": model,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "cost_usd": cost_usd,
        "latency_ms": latency_ms,
        "usage_available": usage_available,
    }
    telemetry.update({key: value for key, value in extra.items() if value is not None})
    return telemetry


def _record_telemetry(state: WorkflowState, step_data: StepTelemetry) -> dict[str, Any]:
    telemetry = dict(state.get("telemetry", {}))
    steps = list(telemetry.get("steps", []))
    steps.append(step_data)

    latest_error = next((item for item in reversed(steps) if item.get("error_type") or item.get("error_message")), {})
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
            "error_type": latest_error.get("error_type"),
            "error_message": latest_error.get("error_message"),
            "error_details": latest_error.get("error_details"),
        }
    )
    return telemetry


def _merge_state(state: WorkflowState, update: WorkflowState) -> WorkflowState:
    merged = WorkflowState(state)
    merged.update(update)
    return merged


def _append_trace(
    state: WorkflowState,
    step: str,
    status: str,
    detail: str,
) -> list[WorkflowTrace]:
    trace = list(state.get("trace", []))
    trace.append(
        {
            "step": step,
            "status": status,
            "detail": detail,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "phase": step,
        }
    )
    return trace


def _skip_optional_reflection(state: WorkflowState) -> WorkflowState:
    return {
        "telemetry": _record_telemetry(
            state,
            _new_step_telemetry(
                step="reflection",
                model="workflow",
                usage_available=False,
            ),
        ),
        "trace": _append_trace(
            state,
            "reflection",
            "skipped",
            "No self-correction required after successful validation.",
        ),
    }


def _emit_event(
    callback: WorkflowEventCallback | None,
    phase: str,
    state: WorkflowState,
    step: str,
    detail: str,
) -> None:
    if callback is None:
        return
    event = {
        "phase": step,
        "status": phase,
        "step": step,
        "detail": detail,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "perf_counter": time.perf_counter(),
    }
    snapshot = WorkflowState(state)
    snapshot["event"] = event
    callback(phase, snapshot, step, detail)


def _emit_token_event(
    callback: WorkflowEventCallback | None,
    state: WorkflowState,
    step: str,
    token: str,
    accumulated: str,
    started: float,
) -> None:
    if callback is None:
        return
    approx_completion_tokens = max(1, len(accumulated.split()))
    base_telemetry = dict(state.get("telemetry", {}))
    base_steps = list(base_telemetry.get("steps", []))
    partial_telemetry = {
        **base_telemetry,
        "steps": base_steps,
        "model": base_telemetry.get("model") or DEFAULT_SQL_MODEL,
        "completion_tokens": base_telemetry.get("completion_tokens", 0) + approx_completion_tokens,
        "total_tokens": base_telemetry.get("total_tokens", 0) + approx_completion_tokens,
        "latency_ms": base_telemetry.get("latency_ms", 0) + int((time.perf_counter() - started) * 1000),
        "usage_available": base_telemetry.get("usage_available", False),
    }
    event = {
        "phase": step,
        "status": "streaming",
        "step": step,
        "detail": "Streaming assistant response.",
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "token": token,
        "content": accumulated,
        "telemetry": partial_telemetry,
    }
    snapshot = WorkflowState(state)
    snapshot["event"] = event
    snapshot["telemetry"] = partial_telemetry
    callback("streaming", snapshot, step, "Streaming assistant response.")


def planner_node(state: WorkflowState) -> WorkflowState:
    question = state["question"].strip()
    followup_context = contextualize_followup(question, state.get("conversation_context"))
    effective_question = followup_context.get("effective_question") or question
    detail = "Follow-up prompt contextualized from analytics memory." if followup_context.get("is_followup") else "Question analyzed for SQL planning."
    return {
        "effective_question": effective_question,
        "followup_context": followup_context,
        "plan": {"intent": effective_question, "original_question": question},
        "trace": _append_trace(
            state,
            "planner",
            "success",
            detail,
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
    examples = retrieve_similar_queries(state.get("effective_question") or state["question"], top_k=3)
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
    question = state.get("effective_question") or state["question"]
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

    semantic_block = state.get("semantic_context", {}).get("prompt_block", "")
    conversation_block = memory_prompt_block(state.get("conversation_context"))
    workspace_block = workspace_prompt_block(state.get("workspace_context"), question)

    if state.get("last_error") and state.get("last_failed_sql"):
        return f"""{question}

Previous SQL failed:
{state['last_failed_sql']}

Database error:
{state['last_error']}

Generate a corrected read-only SQL query.{memory_block}{semantic_block}{conversation_block}{workspace_block}"""
    return f"{question}{memory_block}{semantic_block}{conversation_block}{workspace_block}"


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
{state.get('effective_question') or state['question']}

Database schema:
{state['schema']}

Failed SQL:
{state.get('last_failed_sql', '')}

Database/runtime error:
{state.get('last_error', '')}

Error source:
{state.get('last_error_source', 'unknown')}

Return ONLY corrected read-only SQL. Do not explain anything.{memory_block}{state.get("semantic_context", {}).get("prompt_block", "")}{memory_prompt_block(state.get("conversation_context"))}{workspace_prompt_block(state.get("workspace_context"), state.get("effective_question") or state["question"])}"""


def sql_generation_node(
    state: WorkflowState,
    callback: WorkflowEventCallback | None = None,
) -> WorkflowState:
    if state.get("error") and state.get("retry_count", 0) > MAX_RETRIES:
        return {}

    started = time.perf_counter()

    def on_token(token: str, accumulated: str) -> None:
        _emit_token_event(callback, state, "sql generation", token, accumulated, started)

    if callback is not None:
        generation_result = stream_sql_with_telemetry(
            _build_generation_prompt(state),
            state["schema"],
            token_callback=on_token,
        )
    else:
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


def reflection_node(
    state: WorkflowState,
    callback: WorkflowEventCallback | None = None,
) -> WorkflowState:
    retry_count = state.get("retry_count", 0) + 1
    started = time.perf_counter()

    def on_token(token: str, accumulated: str) -> None:
        _emit_token_event(callback, state, "reflection", token, accumulated, started)

    if callback is not None:
        reflection_result = stream_sql_with_telemetry(
            _build_reflection_prompt(state),
            state["schema"],
            token_callback=on_token,
        )
    else:
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


def reflection_skip_node(state: WorkflowState) -> WorkflowState:
    if any(item.get("step") == "reflection" for item in state.get("trace", [])):
        return {}
    return _skip_optional_reflection(state)


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
    graph.add_node("reflection_skip", reflection_skip_node)
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
            "execution": "reflection_skip",
            "end": END,
        },
    )
    graph.add_edge("reflection_skip", "execution")
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


def _run_linear(
    question: str,
    callback: WorkflowEventCallback | None = None,
    semantic_context: dict[str, Any] | None = None,
    conversation_context: dict[str, Any] | None = None,
    workspace_context: dict[str, Any] | None = None,
) -> WorkflowState:
    state: WorkflowState = {
        "question": question,
        "error": None,
        "retry_count": 0,
        "last_error": None,
        "last_error_source": None,
        "last_failed_sql": "",
        "semantic_context": semantic_context or {},
        "conversation_context": conversation_context or {},
        "workspace_context": workspace_context or {},
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

    _emit_event(callback, "active", state, "planner", "Analyzing question intent.")
    state.update(planner_node(state))
    _emit_event(callback, "completed", state, "planner", "Question analyzed for SQL planning.")
    if state.get("error"):
        return state

    _emit_event(callback, "active", state, "schema retrieval", "Loading database schema context.")
    state.update(schema_node(state))
    _emit_event(
        callback,
        "completed" if not state.get("error") else "warning",
        state,
        "schema retrieval",
        state.get("trace", [{}])[-1].get("detail", "Schema retrieval finished."),
    )
    if state.get("error"):
        return state

    _emit_event(callback, "active", state, "memory retrieval", "Retrieving similar examples from memory.")
    state.update(memory_node(state))
    _emit_event(
        callback,
        "completed",
        state,
        "memory retrieval",
        state.get("trace", [{}])[-1].get("detail", "Memory retrieval finished."),
    )
    if state.get("error"):
        return state

    while True:
        _emit_event(callback, "active", state, "sql generation", "Generating SQL candidate.")
        state.update(sql_generation_node(state, callback=callback))
        _emit_event(
            callback,
            "completed" if not state.get("error") else "warning",
            state,
            "sql generation",
            state.get("trace", [{}])[-1].get("detail", "SQL generation finished."),
        )
        if state.get("error"):
            return state

        _emit_event(callback, "active", state, "validation", "Running SQL safety validation.")
        state.update(validation_node(state))
        _emit_event(
            callback,
            "completed" if not state.get("error") else "warning",
            state,
            "validation",
            state.get("trace", [{}])[-1].get("detail", "Validation finished."),
        )
        if state.get("error"):
            if state.get("retry_count", 0) < MAX_RETRIES:
                _emit_event(callback, "active", state, "reflection", "Repairing SQL after validation failure.")
                state.update(reflection_node(state, callback=callback))
                _emit_event(
                    callback,
                    "completed" if not state.get("error") else "warning",
                    state,
                    "reflection",
                    state.get("trace", [{}])[-1].get("detail", "Reflection finished."),
                )
                if state.get("error"):
                    return state
                continue
            return state

        if not any(item.get("step") == "reflection" for item in state.get("trace", [])):
            state.update(_skip_optional_reflection(state))
            _emit_event(
                callback,
                "skipped",
                state,
                "reflection",
                "No self-correction required after successful validation.",
            )

        _emit_event(callback, "active", state, "execution", "Executing SQL against the database.")
        state.update(execution_node(state))
        _emit_event(
            callback,
            "completed" if not state.get("error") else "warning",
            state,
            "execution",
            state.get("trace", [{}])[-1].get("detail", "Execution finished."),
        )
        if state.get("error") and state.get("retry_count", 0) < MAX_RETRIES:
            _emit_event(callback, "active", state, "reflection", "Repairing SQL after execution failure.")
            state.update(reflection_node(state, callback=callback))
            _emit_event(
                callback,
                "completed" if not state.get("error") else "warning",
                state,
                "reflection",
                state.get("trace", [{}])[-1].get("detail", "Reflection finished."),
            )
            if state.get("error"):
                return state
            continue
        return state


def run_workflow(
    question: str,
    callback: WorkflowEventCallback | None = None,
    semantic_context: dict[str, Any] | None = None,
    conversation_context: dict[str, Any] | None = None,
    workspace_context: dict[str, Any] | None = None,
) -> WorkflowState:
    initial_state: WorkflowState = {
        "question": question,
        "error": None,
        "retry_count": 0,
        "last_error": None,
        "last_error_source": None,
        "last_failed_sql": "",
        "memory_examples": [],
        "semantic_context": semantic_context or {},
        "conversation_context": conversation_context or {},
        "workspace_context": workspace_context or {},
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

    if callback is not None or workflow is None:
        return _run_linear(
            question,
            callback=callback,
            semantic_context=semantic_context,
            conversation_context=conversation_context,
            workspace_context=workspace_context,
        )

    result = workflow.invoke(initial_state)
    return WorkflowState(result)
