from __future__ import annotations

import sqlite3

import pytest

import graph.workflow as workflow_module


def test_linear_workflow_preserves_correlation_id_with_mocked_llm(monkeypatch) -> None:
    def fake_sql(question, schema, model=workflow_module.DEFAULT_SQL_MODEL, token_callback=None):
        return {
            "sql": "SELECT CustomerId, FirstName FROM Customer LIMIT 5",
            "telemetry": {
                "model": model,
                "prompt_tokens": 8,
                "completion_tokens": 7,
                "total_tokens": 15,
                "cost_usd": 0.001,
                "latency_ms": 10,
                "usage_available": True,
            },
        }

    monkeypatch.setattr(workflow_module, "stream_sql_with_telemetry", fake_sql)
    monkeypatch.setattr(workflow_module, "retrieve_similar_queries", lambda *args, **kwargs: [])
    monkeypatch.setattr(workflow_module, "save_query_to_history", lambda *args, **kwargs: None)
    monkeypatch.setattr(workflow_module, "log_query_cost", lambda *args, **kwargs: None)
    result = workflow_module.run_workflow("List customers", callback=lambda *_: None)

    assert result["error"] is None
    assert result["telemetry"]["correlation_id"].startswith("wf-")
    assert result["telemetry"]["schema_version"]
    assert any(item["step"] == "sql generation" for item in result["telemetry"]["steps"])
    assert result["sql_validation"]["status"] in {"passed", "warning"}
    assert result["sql_explanation"]["intent_summary"]
    assert result["result_quality"]["status"] in {"passed", "warning"}


@pytest.fixture
def sales_workflow(monkeypatch):
    """Exercise the real planner/validator/executor without API or history writes."""
    connection = sqlite3.connect(":memory:")
    connection.execute("CREATE TABLE Sales (revenue REAL)")
    connection.executemany("INSERT INTO Sales VALUES (?)", [(100.0,), (200.0,)])
    executed_sql = []
    model_calls = []

    def execute(sql):
        executed_sql.append(sql)
        cursor = connection.execute(sql)
        return [column[0] for column in cursor.description], cursor.fetchall()

    def configure_responses(initial_sql, repaired_sql):
        def fake_sql(question, schema, model=workflow_module.DEFAULT_SQL_MODEL, token_callback=None):
            is_repair = question.startswith("You are fixing a failed SQL query")
            model_calls.append(("reflection" if is_repair else "generation", model))
            return {
                "sql": repaired_sql if is_repair else initial_sql,
                "telemetry": {
                    "model": model,
                    "prompt_tokens": 8,
                    "completion_tokens": 7,
                    "total_tokens": 15,
                    "cost_usd": 0.001,
                    "latency_ms": 10,
                    "usage_available": True,
                },
            }

        monkeypatch.setattr(workflow_module, "stream_sql_with_telemetry", fake_sql)
        monkeypatch.setattr(workflow_module, "generate_sql_with_telemetry", fake_sql)

    monkeypatch.setenv("ORCHESTRATION_MAX_RETRIES", "2")
    monkeypatch.setattr(workflow_module, "get_schema", lambda: "Table: Sales\nrevenue (REAL)")
    monkeypatch.setattr(workflow_module, "run_query", execute)
    monkeypatch.setattr(workflow_module, "retrieve_similar_queries", lambda *args, **kwargs: [])
    monkeypatch.setattr(workflow_module, "save_query_to_history", lambda *args, **kwargs: None)
    monkeypatch.setattr(workflow_module, "log_query_cost", lambda *args, **kwargs: None)
    yield configure_responses, executed_sql, model_calls, connection
    connection.close()


@pytest.mark.parametrize("streaming", [True, False])
def test_recovery_executes_repaired_sql_and_preserves_selected_model(sales_workflow, streaming):
    configure, executed_sql, model_calls, _ = sales_workflow
    repaired_sql = "SELECT SUM(revenue) AS revenue FROM Sales LIMIT 1"
    configure("SELECT revenue FROM MissingTable LIMIT 1", repaired_sql)

    result = workflow_module.run_workflow(
        "What is total revenue?",
        callback=(lambda *_: None) if streaming else None,
        model="test-selected-model",
    )

    assert result["error"] is None
    assert result["rows"] == [(300.0,)]
    assert result["sql"] == repaired_sql
    assert result["retry_count"] == 1
    assert executed_sql == [repaired_sql]
    assert model_calls == [("generation", "test-selected-model"), ("reflection", "test-selected-model")]


def test_linear_recovery_revalidates_sql_after_database_error(sales_workflow):
    configure, executed_sql, model_calls, _ = sales_workflow
    initial_sql = "SELECT missing_function(revenue) FROM Sales LIMIT 1"
    repaired_sql = "SELECT SUM(revenue) AS revenue FROM Sales LIMIT 1"
    configure(initial_sql, repaired_sql)

    result = workflow_module.run_workflow("What is total revenue?", callback=lambda *_: None)

    assert result["error"] is None
    assert result["rows"] == [(300.0,)]
    assert executed_sql == [initial_sql, repaired_sql]
    assert [kind for kind, _ in model_calls] == ["generation", "reflection"]
    assert len([step for step in result["trace"] if step["step"] == "validation"]) == 2


@pytest.mark.parametrize(
    "initial_sql,expected_executions",
    [
        ("SELECT revenue FROM MissingTable LIMIT 1", []),
        ("SELECT missing_function(revenue) FROM Sales LIMIT 1", ["SELECT missing_function(revenue) FROM Sales LIMIT 1"]),
    ],
)
def test_linear_recovery_blocks_unsafe_repair(sales_workflow, monkeypatch, initial_sql, expected_executions):
    configure, executed_sql, model_calls, connection = sales_workflow
    monkeypatch.setenv("ORCHESTRATION_MAX_RETRIES", "1")
    configure(initial_sql, "DELETE FROM Sales")

    result = workflow_module.run_workflow("What is total revenue?", callback=lambda *_: None)

    assert result["error"]
    assert result["sql_validation"]["status"] == "failed"
    assert result["retry_count"] == 1
    assert executed_sql == expected_executions
    assert [kind for kind, _ in model_calls] == ["generation", "reflection"]
    assert connection.execute("SELECT SUM(revenue) FROM Sales").fetchone() == (300.0,)


def test_linear_recovery_stops_when_repair_budget_is_exhausted(sales_workflow):
    configure, executed_sql, model_calls, _ = sales_workflow
    configure("SELECT revenue FROM MissingTable LIMIT 1", "SELECT revenue FROM StillMissing LIMIT 1")

    result = workflow_module.run_workflow("What is total revenue?", callback=lambda *_: None)

    assert result["error"]
    assert "StillMissing" in result["last_error"]
    assert result["retry_count"] == 2
    assert executed_sql == []
    assert [kind for kind, _ in model_calls] == ["generation", "reflection", "reflection"]


def test_linear_recovery_stops_when_model_cannot_repair(sales_workflow):
    configure, executed_sql, model_calls, _ = sales_workflow
    configure("SELECT revenue FROM MissingTable LIMIT 1", "ERROR: model request failed")

    result = workflow_module.run_workflow("What is total revenue?", callback=lambda *_: None)

    assert result["error"] == "ERROR: model request failed"
    assert result["retry_count"] == 1
    assert executed_sql == []
    assert [kind for kind, _ in model_calls] == ["generation", "reflection"]
