from __future__ import annotations

from backend.telemetry import phase_latency_breakdown, telemetry_event, telemetry_export_rows, validate_telemetry_payload


def test_validate_telemetry_payload_adds_correlation_and_totals() -> None:
    telemetry = validate_telemetry_payload(
        {
            "steps": [
                {"step": "memory retrieval", "model": "chromadb", "latency_ms": 12},
                {
                    "step": "sql generation",
                    "model": "gpt-4o-mini",
                    "prompt_tokens": 10,
                    "completion_tokens": 5,
                    "total_tokens": 15,
                    "latency_ms": 120,
                    "cost_usd": 0.001,
                    "usage_available": True,
                },
            ]
        }
    )

    assert telemetry["schema_version"]
    assert telemetry["correlation_id"].startswith("wf-")
    assert telemetry["total_tokens"] == 15
    assert telemetry["latency_ms"] == 132
    assert telemetry["model"] == "gpt-4o-mini"


def test_telemetry_export_rows_join_trace_status() -> None:
    telemetry = validate_telemetry_payload({"correlation_id": "wf-test", "steps": [{"step": "execution"}]})
    rows = telemetry_export_rows(telemetry, [{"step": "execution", "status": "success", "detail": "ok"}])

    assert rows[0]["correlation_id"] == "wf-test"
    assert rows[0]["status"] == "success"
    assert rows[0]["detail"] == "ok"


def test_phase_latency_breakdown_and_events() -> None:
    telemetry = validate_telemetry_payload({"steps": [{"step": "sql generation", "latency_ms": 44}]})
    breakdown = phase_latency_breakdown(telemetry)
    event = telemetry_event(
        correlation_id=telemetry["correlation_id"],
        workflow_id="streamlit-local",
        phase="sql generation",
        status="completed",
        message="generated",
        step={"latency_ms": 44},
    )

    assert breakdown[0]["phase"] == "sql generation"
    assert breakdown[0]["latency_ms"] == 44
    assert event["event_id"].startswith("evt-")
    assert event["correlation_id"] == telemetry["correlation_id"]
