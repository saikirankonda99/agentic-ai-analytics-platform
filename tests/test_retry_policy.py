from __future__ import annotations

from backend.retry import RetryPolicy, retry_decision, retry_delay, retry_diagnostics, retry_policy


def test_retry_delay_uses_deterministic_exponential_backoff() -> None:
    policy = RetryPolicy(
        domain="workflow",
        max_retries=3,
        base_delay_seconds=0.5,
        max_delay_seconds=2.0,
        backoff_multiplier=2.0,
    )

    assert retry_delay(policy, 1) == 0.5
    assert retry_delay(policy, 2) == 1.0
    assert retry_delay(policy, 3) == 2.0
    assert retry_delay(policy, 4) == 2.0


def test_retry_decision_respects_budget() -> None:
    policy = RetryPolicy(domain="workflow", max_retries=2, base_delay_seconds=0.1)

    first = retry_decision(domain="workflow", retry_count=0, error="failed", policy=policy)
    exhausted = retry_decision(domain="workflow", retry_count=2, error="failed", policy=policy)

    assert first.should_retry is True
    assert first.delay_seconds == 0.1
    assert exhausted.should_retry is False
    assert exhausted.delay_seconds == 0.0


def test_retry_policy_uses_domain_environment(monkeypatch) -> None:
    monkeypatch.setenv("ORCHESTRATION_MAX_RETRIES", "4")
    monkeypatch.setenv("OPENAI_MAX_ATTEMPTS", "3")

    assert retry_policy("workflow").max_retries == 4
    assert retry_policy("workflow").max_attempts == 5
    assert retry_policy("llm").max_retries == 2
    assert retry_policy("llm").max_attempts == 3


def test_retry_diagnostics_expose_all_runtime_domains() -> None:
    diagnostics = retry_diagnostics()

    assert diagnostics["deterministic_backoff"] is True
    assert {"workflow", "llm", "ats", "persistence"}.issubset(diagnostics)
