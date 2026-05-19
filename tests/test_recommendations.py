from __future__ import annotations

from backend.recommendations import autonomous_recommendations, recommendation_messages


def test_recommendations_prioritize_runtime_anomalies() -> None:
    cards = autonomous_recommendations(
        operations={"error_rate": 25, "avg_latency_ms": 6000},
        memory={"query_history": [{"question": "show revenue"}]},
        investigation={"severity": "critical"},
        telemetry={"error_type": "AuthenticationError"},
    )

    categories = {card["category"] for card in cards}
    assert "anomaly_alert" in categories
    assert "optimization" in categories
    assert "investigation_escalation" in categories
    assert recommendation_messages(cards)
