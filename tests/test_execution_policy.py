from __future__ import annotations

from backend.policies import ExecutionPolicy, evaluate_stage_policy


def test_policy_retries_while_budget_remains() -> None:
    decision = evaluate_stage_policy(
        stage="sql generation",
        confidence=0.2,
        retry_count=0,
        error="connection failed",
        policy=ExecutionPolicy(max_retries=2),
    )

    assert decision["action"] == "retry"
    assert decision["max_retries"] == 2


def test_policy_escalates_critical_stage_after_retry_budget() -> None:
    decision = evaluate_stage_policy(
        stage="execution",
        confidence=0.1,
        retry_count=2,
        error="database failed",
        policy=ExecutionPolicy(max_retries=2),
    )

    assert decision["action"] == "escalate"


def test_policy_monitors_low_confidence_success() -> None:
    decision = evaluate_stage_policy(
        stage="memory retrieval",
        confidence=0.2,
        policy=ExecutionPolicy(confidence_floor=0.55),
    )

    assert decision["action"] == "monitor"
