"""Evaluate the current question-to-SQL workflow against the bundled Chinook data.

Reference and generated SQL are compared by their actual result values, including
duplicate rows and optional ordering. SQL text equality is reported separately;
matching this finite dataset is not a proof of general SQL equivalence. Column
aliases are ignored; column order is checked. Numbers allow an absolute floating
point tolerance of 1e-8, with integer-to-integer comparisons remaining exact.

    python evals/run_evals.py --validate-only  # no model calls
    python evals/run_evals.py --model gpt-4o-mini --limit 3

Running without --validate-only calls the configured model and can incur API
charges. The workflow may persist its usual local history and telemetry.
"""

from __future__ import annotations

import argparse
import json
import math
import sqlite3
import sys
import time
from contextlib import closing
from datetime import datetime, timezone
from numbers import Real
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

GOLDEN_SET_PATH = Path(__file__).parent / "golden_set.json"
RESULTS_DIR = Path(__file__).parent / "results"
DATABASE_PATH = PROJECT_ROOT / "data" / "chinook.db"
MAX_RESULT_ROWS = 2_000


def load_golden_set() -> list[dict[str, Any]]:
    with GOLDEN_SET_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def _read_only_authorizer(action: int, first: str | None, second: str | None, *_: Any) -> int:
    if action == sqlite3.SQLITE_FUNCTION and str(second or first).lower() == "load_extension":
        return sqlite3.SQLITE_DENY
    allowed = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION, sqlite3.SQLITE_RECURSIVE}
    return sqlite3.SQLITE_OK if action in allowed else sqlite3.SQLITE_DENY


def _query_result(sql: str, database_path: Path = DATABASE_PATH) -> tuple[int, list[tuple[Any, ...]]]:
    """Read one bounded query without creating databases or permitting writes/ATTACH."""
    if not sql.strip():
        raise ValueError("SQL is empty.")
    deadline = time.monotonic() + 5.0
    uri = Path(database_path).resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as connection:
        connection.execute("PRAGMA query_only=ON")
        connection.set_authorizer(_read_only_authorizer)
        connection.set_progress_handler(lambda: int(time.monotonic() > deadline), 1_000)
        cursor = connection.execute(sql)
        if cursor.description is None:
            raise ValueError("Evaluation SQL must return a result set.")
        rows = cursor.fetchmany(MAX_RESULT_ROWS + 1)
        if len(rows) > MAX_RESULT_ROWS:
            raise ValueError(f"Evaluation result exceeds {MAX_RESULT_ROWS} rows.")
        return len(cursor.description), rows


def _same_value(left: Any, right: Any) -> bool:
    if isinstance(left, int) and isinstance(right, int):
        return left == right
    if isinstance(left, Real) and isinstance(right, Real):
        return math.isclose(left, right, rel_tol=0.0, abs_tol=1e-8)
    return type(left) is type(right) and left == right


def _same_row(left: tuple[Any, ...], right: tuple[Any, ...]) -> bool:
    return len(left) == len(right) and all(_same_value(a, b) for a, b in zip(left, right))


def _same_results(
    generated: tuple[int, list[tuple[Any, ...]]],
    expected: tuple[int, list[tuple[Any, ...]]],
    *,
    order_matters: bool,
) -> bool:
    generated_columns, generated_rows = generated
    expected_columns, expected_rows = expected
    if generated_columns != expected_columns or len(generated_rows) != len(expected_rows):
        return False
    if order_matters:
        return all(_same_row(left, right) for left, right in zip(generated_rows, expected_rows))
    # Preserve duplicate counts; aliases may differ, but selected column order must match.
    unmatched = list(expected_rows)
    for row in generated_rows:
        match = next((i for i, expected_row in enumerate(unmatched) if _same_row(row, expected_row)), None)
        if match is None:
            return False
        unmatched.pop(match)
    return True


def _semantic_match(
    generated_sql: str,
    expected_sql: str,
    item: dict[str, Any],
    database_path: Path = DATABASE_PATH,
) -> bool:
    return _same_results(
        _query_result(generated_sql, database_path),
        _query_result(expected_sql, database_path),
        order_matters=bool(item.get("order_matters", False)),
    )


def validate_golden_set(items: list[dict[str, Any]]) -> list[str]:
    errors = []
    for index, item in enumerate(items, start=1):
        try:
            if not str(item.get("question", "")).strip():
                raise ValueError("Question is empty.")
            _query_result(str(item.get("expected_sql", "")))
        except (sqlite3.Error, ValueError) as exc:
            errors.append(f"{item.get('id', index)}: {type(exc).__name__}: {exc}")
    return errors


def _run_pipeline(question: str, model: str | None) -> dict[str, Any]:
    # Import only for actual evaluations, so --validate-only never initializes the LLM runtime.
    from graph.workflow import run_workflow
    from backend.connectors import get_connector_registry

    connector = get_connector_registry().get("sqlite")
    if connector.database_path.resolve() != DATABASE_PATH.resolve():
        raise ValueError("SQLITE_DATABASE_PATH must select the bundled Chinook database for these evaluations.")
    options = {"model": model} if model else {}
    return run_workflow(question, **options)


def run_single(item: dict[str, Any], *, model: str | None = None) -> dict[str, Any]:
    started = time.perf_counter()
    result: dict[str, Any] = {
        "id": item.get("id"),
        "question": str(item.get("question", "")),
        "expected_sql": str(item.get("expected_sql", "")),
        "generated_sql": "",
        "exact_match": False,
        "semantic_match": False,
        "valid": False,
        "safe": False,
        "reflection_iterations": 0,
        "latency_ms": 0,
        "cost_usd": 0.0,
        "tokens_used": 0,
        "model_requested": model,
        "model_used": "",
        "error": None,
    }
    try:
        if not result["question"].strip():
            raise ValueError("Question is empty.")
        expected = _query_result(result["expected_sql"])
        state = _run_pipeline(result["question"], model)
        telemetry = state.get("telemetry") or {}
        generated_sql = str(state.get("sql", "")).strip()
        result.update(
            generated_sql=generated_sql,
            reflection_iterations=int(state.get("retry_count") or 0),
            cost_usd=float(telemetry.get("cost_usd") or 0.0),
            tokens_used=int(telemetry.get("total_tokens") or 0),
            model_used=telemetry.get("model", ""),
            correlation_id=telemetry.get("correlation_id"),
            validation_status=(state.get("sql_validation") or {}).get("status"),
        )
        if state.get("error"):
            raise RuntimeError(str(state["error"]))
        generated = _query_result(generated_sql)
        result.update(
            valid=True,
            safe=True,  # The statement executed under the read-only SQLite authorizer.
            exact_match=generated_sql == result["expected_sql"].strip(),
            semantic_match=_same_results(generated, expected, order_matters=bool(item.get("order_matters", False))),
        )
    except Exception as exc:
        # Preserve a complete failed record; one bad case must not break summary generation.
        result["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        result["latency_ms"] = round((time.perf_counter() - started) * 1_000)
    return result


def summarise(results: list[dict[str, Any]]) -> dict[str, Any]:
    if not results:
        return {"total": 0, "errors": 0}
    count = len(results)
    latencies = [float(item.get("latency_ms", 0)) for item in results]
    costs = [float(item.get("cost_usd", 0)) for item in results]
    return {
        "total": count,
        "errors": sum(bool(item.get("error")) for item in results),
        "exact_match_pct": round(sum(item.get("exact_match") is True for item in results) / count * 100, 1),
        "semantic_match_pct": round(sum(item.get("semantic_match") is True for item in results) / count * 100, 1),
        "valid_sql_pct": round(sum(item.get("valid") is True for item in results) / count * 100, 1),
        "avg_latency_ms": round(sum(latencies) / count),
        "p95_latency_ms": round(sorted(latencies)[math.ceil(count * 0.95) - 1]),
        "total_cost_usd": round(sum(costs), 6),
        "avg_cost_per_query_usd": round(sum(costs) / count, 6),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate question-to-SQL results on the bundled Chinook dataset")
    parser.add_argument("--model", default=None, help="Model passed to the workflow; omitted uses its configured default")
    parser.add_argument("--output", type=Path, default=None, help="Results JSON path")
    parser.add_argument("--limit", type=int, default=None, help="Maximum number of reference questions")
    parser.add_argument("--validate-only", action="store_true", help="Validate reference SQL without any model calls")
    args = parser.parse_args(argv)
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be a positive integer")
    golden = load_golden_set()
    if args.limit is not None:
        golden = golden[:args.limit]
    reference_errors = validate_golden_set(golden)
    if reference_errors:
        print("Reference queries failed; no model calls were made:\n" + "\n".join(reference_errors))
        return 1
    if args.validate_only:
        print(f"Validated {len(golden)} reference queries against data/chinook.db; no model calls were made.")
        return 0

    results = []
    for index, item in enumerate(golden, start=1):
        result = run_single(item, model=args.model)
        results.append(result)
        print(f"[{index}/{len(golden)}] match={result['semantic_match']} error={result['error']} {item['question']}")
    summary = summarise(results)
    print(json.dumps(summary, indent=2))
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    output_path = args.output or RESULTS_DIR / f"run_{timestamp}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps({"summary": summary, "results": results, "model_requested": args.model}, indent=2), encoding="utf-8"
    )
    print(f"Results saved to {output_path}")
    return 0 if all(item["semantic_match"] for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
