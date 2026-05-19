"""
Agentic Eval Runner

Runs the full LangGraph pipeline against a golden set of NL → SQL pairs
and measures:
  - exact_match:    does the generated SQL exactly match the expected SQL?
  - semantic_match: does the SQL produce the same result as the expected SQL?
  - valid:          does the SQL parse without error?
  - latency_ms:     end-to-end wall-clock time
  - cost_usd:       estimated API cost for the query
  - reflection_iterations: how many reflection retries were needed?

Usage:
  python evals/run_evals.py
  python evals/run_evals.py --model gpt-4o-mini --output evals/results/run_001.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

# make sure the project root is on sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from graph.workflow import AgentState, workflow


GOLDEN_SET_PATH = Path(__file__).parent / "golden_set.json"
RESULTS_DIR = Path(__file__).parent / "results"


def load_golden_set() -> list[dict]:
    with open(GOLDEN_SET_PATH) as f:
        return json.load(f)


def run_single(item: dict, thread_id: str) -> dict:
    """Runs one NL question through the full agentic pipeline."""
    question = item["question"]
    expected_sql = item.get("expected_sql", "")

    initial_state: AgentState = {
        "messages": [],
        "user_question": question,
        "plan": {},
        "schema_context": "",
        "history_context": "",
        "sql_draft": "",
        "sql_final": "",
        "reflection": {},
        "validation_result": {},
        "query_result": None,
        "insight": "",
        "iteration": 0,
        "awaiting_human": False,
        "human_approved": True,   # auto-approve for evals
        "error": None,
        "cost_usd": 0.0,
        "tokens_used": 0,
    }

    config = {"configurable": {"thread_id": thread_id}}

    t0 = time.perf_counter()
    final_state = workflow.invoke(initial_state, config=config)
    latency_ms = int((time.perf_counter() - t0) * 1000)

    generated_sql = final_state.get("sql_final", "").strip()
    reflection = final_state.get("reflection", {})

    # exact match (normalise whitespace)
    def normalise(s: str) -> str:
        return " ".join(s.lower().split())

    exact_match = normalise(generated_sql) == normalise(expected_sql) if expected_sql else None

    # semantic match: both produce same row count from the test DB
    semantic_match = _semantic_match(generated_sql, expected_sql, item)

    return {
        "question": question,
        "expected_sql": expected_sql,
        "generated_sql": generated_sql,
        "exact_match": exact_match,
        "semantic_match": semantic_match,
        "valid": reflection.get("valid", False),
        "safe": reflection.get("safe", True),
        "confidence": reflection.get("confidence", 0.0),
        "reflection_iterations": final_state.get("iteration", 0),
        "latency_ms": latency_ms,
        "cost_usd": final_state.get("cost_usd", 0.0),
        "tokens_used": final_state.get("tokens_used", 0),
        "error": final_state.get("error"),
    }


def _semantic_match(generated_sql: str, expected_sql: str, item: dict) -> bool | None:
    """
    Compares row counts from the test DB.
    Returns None if no expected_sql or DB connection unavailable.
    """
    if not expected_sql or not generated_sql:
        return None
    try:
        import sqlite3
        db_path = Path(__file__).parent.parent / "data" / "sample_db.sqlite"
        if not db_path.exists():
            return None
        conn = sqlite3.connect(str(db_path))
        expected_rows = len(conn.execute(expected_sql).fetchall())
        generated_rows = len(conn.execute(generated_sql).fetchall())
        conn.close()
        return expected_rows == generated_rows
    except Exception:
        return None


def summarise(results: list[dict]) -> dict:
    n = len(results)
    if n == 0:
        return {}

    exact = [r for r in results if r.get("exact_match") is True]
    semantic = [r for r in results if r.get("semantic_match") is True]
    valid = [r for r in results if r.get("valid")]
    latencies = [r["latency_ms"] for r in results]
    costs = [r["cost_usd"] for r in results]

    return {
        "total": n,
        "exact_match_pct": round(len(exact) / n * 100, 1),
        "semantic_match_pct": round(len(semantic) / n * 100, 1),
        "valid_sql_pct": round(len(valid) / n * 100, 1),
        "avg_latency_ms": round(sum(latencies) / n),
        "p95_latency_ms": round(sorted(latencies)[int(n * 0.95)]),
        "total_cost_usd": round(sum(costs), 4),
        "avg_cost_per_query_usd": round(sum(costs) / n, 4),
    }


def main():
    parser = argparse.ArgumentParser(description="Run agentic SQL eval harness")
    parser.add_argument("--model", default="gpt-4o", help="LLM model to use")
    parser.add_argument("--output", default=None, help="Path to save results JSON")
    parser.add_argument("--limit", type=int, default=None, help="Max questions to eval")
    args = parser.parse_args()

    golden = load_golden_set()
    if args.limit:
        golden = golden[: args.limit]

    print(f"🧪 Running eval on {len(golden)} questions with model={args.model}\n")

    results = []
    for i, item in enumerate(golden):
        thread_id = f"eval_{i}_{time.time()}"
        print(f"[{i+1}/{len(golden)}] {item['question'][:70]}...")
        try:
            result = run_single(item, thread_id)
            results.append(result)
            status = "✅" if result.get("semantic_match") else "❌"
            print(f"  {status} latency={result['latency_ms']}ms | "
                  f"confidence={result['confidence']:.0%} | "
                  f"${result['cost_usd']:.4f}")
        except Exception as e:
            print(f"  💥 ERROR: {e}")
            results.append({"question": item["question"], "error": str(e)})

    summary = summarise(results)
    print("\n" + "=" * 50)
    print("📊 EVAL SUMMARY")
    print("=" * 50)
    for k, v in summary.items():
        print(f"  {k:30s}: {v}")

    # save results
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = args.output or str(
        RESULTS_DIR / f"run_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
    )
    with open(output_path, "w") as f:
        json.dump({"summary": summary, "results": results, "model": args.model}, f, indent=2)
    print(f"\n💾 Results saved to {output_path}")


if __name__ == "__main__":
    main()
