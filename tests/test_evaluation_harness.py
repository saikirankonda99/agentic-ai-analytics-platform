from __future__ import annotations

import json
import sqlite3

import pytest

from evals import run_evals


@pytest.fixture
def evaluation_database(tmp_path):
    path = tmp_path / "evaluation.db"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE amounts (id INTEGER PRIMARY KEY, amount INTEGER)")
        connection.executemany("INSERT INTO amounts VALUES (?, ?)", [(1, 10), (2, 10), (3, 20)])
    return path


def test_same_row_count_with_wrong_values_fails(evaluation_database):
    assert not run_evals._semantic_match(
        "SELECT amount + 1 FROM amounts", "SELECT amount FROM amounts", {}, evaluation_database
    )
    # Large integer business identifiers must not be rounded to the same float.
    assert not run_evals._semantic_match(
        "SELECT 9007199254740992", "SELECT 9007199254740993", {}, evaluation_database
    )


def test_result_comparison_preserves_duplicates_columns_and_requested_order(evaluation_database):
    ascending = "SELECT amount FROM amounts ORDER BY amount ASC"
    descending = "SELECT amount FROM amounts ORDER BY amount DESC"
    assert run_evals._semantic_match(ascending, descending, {}, evaluation_database)
    assert not run_evals._semantic_match(ascending, descending, {"order_matters": True}, evaluation_database)
    assert not run_evals._semantic_match(
        "SELECT 10 UNION ALL SELECT 10", "SELECT 10 UNION ALL SELECT 20", {}, evaluation_database
    )
    assert not run_evals._semantic_match("SELECT 1, 2", "SELECT 1", {}, evaluation_database)
    assert run_evals._semantic_match("SELECT 1 AS generated_name", "SELECT 1 AS expected_name", {}, evaluation_database)


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM amounts",
        "CREATE TABLE dangerous (value INTEGER)",
        "ATTACH DATABASE ':memory:' AS other",
        "PRAGMA user_version = 1",
        "SELECT load_extension('nonexistent-extension')",
    ],
)
def test_evaluation_queries_are_read_only(sql, evaluation_database):
    with pytest.raises(sqlite3.DatabaseError):
        run_evals._query_result(sql, evaluation_database)
    assert run_evals._query_result("SELECT amount FROM amounts ORDER BY id", evaluation_database) == (
        1, [(10,), (10,), (20,)]
    )


def test_evaluation_never_creates_a_missing_database(tmp_path):
    missing = tmp_path / "missing.db"
    with pytest.raises(sqlite3.OperationalError):
        run_evals._query_result("SELECT 1", missing)
    assert not missing.exists()


def test_current_workflow_result_fields_and_model_are_used(monkeypatch):
    calls = []

    def fake_pipeline(question, model):
        calls.append((question, model))
        return {
            "sql": "SELECT 2 AS answer",
            "retry_count": 1,
            "telemetry": {"total_tokens": 11, "cost_usd": 0.01, "model": "selected-model"},
            "sql_validation": {"status": "valid"},
            "error": None,
        }

    monkeypatch.setattr(run_evals, "_run_pipeline", fake_pipeline)
    result = run_evals.run_single(
        {"id": "mismatch", "question": "Return one", "expected_sql": "SELECT 1 AS answer"}, model="selected-model"
    )
    assert calls == [("Return one", "selected-model")]
    assert result["valid"] is True
    assert result["semantic_match"] is False
    assert result["generated_sql"] == "SELECT 2 AS answer"
    assert result["reflection_iterations"] == 1
    assert result["tokens_used"] == 11
    assert result["cost_usd"] == 0.01
    assert result["model_used"] == "selected-model"
    assert result["error"] is None


def test_model_selection_reaches_the_workflow_without_live_calls(monkeypatch):
    import graph.workflow as workflow

    calls = []

    def fake_workflow(question, **options):
        calls.append((question, options))
        return {"sql": "SELECT 1"}

    monkeypatch.setattr(workflow, "run_workflow", fake_workflow)
    assert run_evals._run_pipeline("Question", "selected-model") == {"sql": "SELECT 1"}
    assert calls == [("Question", {"model": "selected-model"})]


def test_pipeline_failures_remain_summarizable(monkeypatch):
    def fail_pipeline(*_):
        raise RuntimeError("model unavailable")

    monkeypatch.setattr(run_evals, "_run_pipeline", fail_pipeline)
    result = run_evals.run_single({"id": "failure", "question": "Count", "expected_sql": "SELECT 1"})
    assert result["error"] == "RuntimeError: model unavailable"
    assert result["semantic_match"] is False
    assert result["valid"] is False
    summary = run_evals.summarise([result])
    assert summary["errors"] == 1
    assert summary["semantic_match_pct"] == 0.0
    assert summary["total_cost_usd"] == 0.0


def test_invalid_reference_fails_before_model_invocation(monkeypatch):
    def unexpected_pipeline(*_):
        pytest.fail("Invalid reference SQL must not invoke the model")

    monkeypatch.setattr(run_evals, "_run_pipeline", unexpected_pipeline)
    result = run_evals.run_single({"question": "Count", "expected_sql": "SELECT * FROM missing_reference_table"})
    assert "no such table" in result["error"]
    assert result["semantic_match"] is False


def test_bundled_reference_validation_needs_no_model_calls(monkeypatch, capsys):
    def unexpected_pipeline(*_):
        pytest.fail("Reference-only validation must not invoke the model")

    monkeypatch.setattr(run_evals, "_run_pipeline", unexpected_pipeline)
    assert len(run_evals.load_golden_set()) == 20
    assert run_evals.main(["--validate-only"]) == 0
    assert "20 reference queries" in capsys.readouterr().out


def test_cli_reports_mismatches_with_nonzero_exit_and_complete_output(monkeypatch, tmp_path):
    monkeypatch.setattr(
        run_evals, "load_golden_set", lambda: [{"id": "bad", "question": "Return one", "expected_sql": "SELECT 1"}]
    )
    monkeypatch.setattr(run_evals, "_run_pipeline", lambda *_: {"sql": "SELECT 2"})
    output = tmp_path / "results" / "evaluation.json"
    assert run_evals.main(["--model", "test-model", "--output", str(output)]) == 1
    payload = json.loads(output.read_text())
    assert payload["summary"]["semantic_match_pct"] == 0.0
    assert payload["results"][0]["valid"] is True
    assert payload["model_requested"] == "test-model"
