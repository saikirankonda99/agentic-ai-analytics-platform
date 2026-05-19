from __future__ import annotations

from typing import Any


def autonomous_recommendations(
    *,
    operations: dict[str, Any] | None = None,
    memory: dict[str, Any] | None = None,
    investigation: dict[str, Any] | None = None,
    telemetry: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    operations = operations or {}
    memory = memory or {}
    investigation = investigation or {}
    telemetry = telemetry or {}
    cards: list[dict[str, str]] = []

    if operations.get("error_rate", 0) > 10 or telemetry.get("error_type"):
        cards.append(
            {
                "category": "anomaly_alert",
                "priority": "high",
                "title": "Review runtime failure clusters",
                "detail": "Recent telemetry includes failed workflow signals. Inspect phase-level errors before increasing workload.",
            }
        )

    if operations.get("avg_latency_ms", 0) > 5000:
        cards.append(
            {
                "category": "optimization",
                "priority": "medium",
                "title": "Profile orchestration latency",
                "detail": "Rolling latency is above the operating target. Compare retrieval, model, and execution phases.",
            }
        )

    if len(memory.get("query_history", [])) >= 2:
        latest = memory.get("query_history", [])[-1]
        cards.append(
            {
                "category": "follow_up",
                "priority": "medium",
                "title": "Chain a follow-up analysis",
                "detail": f"Use the latest workflow context to drill into: {latest.get('question', 'the current result')}",
            }
        )

    if investigation.get("severity") in {"warning", "critical"}:
        cards.append(
            {
                "category": "investigation_escalation",
                "priority": "high",
                "title": "Promote investigation evidence",
                "detail": "Persist the reasoning trace and evidence set before presenting the executive summary.",
            }
        )

    if not memory.get("semantic_dataset_memory"):
        cards.append(
            {
                "category": "schema_awareness",
                "priority": "low",
                "title": "Build schema memory baseline",
                "detail": "Run a representative workflow to seed semantic schema and workflow memory for future retrieval.",
            }
        )

    if not cards:
        cards.append(
            {
                "category": "platform_health",
                "priority": "low",
                "title": "Maintain operational baseline",
                "detail": "Runtime metrics are stable. Continue collecting workflow traces for trend analysis.",
            }
        )

    return cards[:5]


def recommendation_messages(cards: list[dict[str, str]]) -> list[str]:
    return [f"{card.get('title', 'Recommendation')}: {card.get('detail', '')}" for card in cards]


__all__ = ["autonomous_recommendations", "recommendation_messages"]
