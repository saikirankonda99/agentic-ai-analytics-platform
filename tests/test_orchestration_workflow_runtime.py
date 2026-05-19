from __future__ import annotations

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
    result = workflow_module.run_workflow("List customers", callback=lambda *_: None)

    assert result["error"] is None
    assert result["telemetry"]["correlation_id"].startswith("wf-")
    assert result["telemetry"]["schema_version"]
    assert any(item["step"] == "sql generation" for item in result["telemetry"]["steps"])
    assert result["sql_validation"]["status"] in {"passed", "warning"}
    assert result["sql_explanation"]["intent_summary"]
    assert result["result_quality"]["status"] in {"passed", "warning"}
