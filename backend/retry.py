from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from typing import Any, Literal


RetryDomain = Literal["workflow", "llm", "ats", "persistence"]


@dataclass(frozen=True)
class RetryPolicy:
    domain: RetryDomain
    max_retries: int = 2
    base_delay_seconds: float = 0.4
    max_delay_seconds: float = 3.0
    backoff_multiplier: float = 2.0

    @property
    def max_attempts(self) -> int:
        return self.max_retries + 1

    def as_dict(self) -> dict[str, Any]:
        return asdict(self) | {"max_attempts": self.max_attempts}


@dataclass(frozen=True)
class RetryDecision:
    domain: RetryDomain
    attempt: int
    max_attempts: int
    retry_count: int
    max_retries: int
    should_retry: bool
    delay_seconds: float
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


def retry_policy(domain: RetryDomain = "workflow") -> RetryPolicy:
    if domain == "llm":
        max_attempts = max(1, _env_int("OPENAI_MAX_ATTEMPTS", _env_int("RETRY_MAX_ATTEMPTS", 2)))
        max_retries = max_attempts - 1
        base_delay = _env_float("OPENAI_RETRY_BASE_DELAY_SECONDS", _env_float("RETRY_BASE_DELAY_SECONDS", 0.4))
    elif domain == "persistence":
        max_retries = max(0, _env_int("DATABASE_RETRIES", _env_int("RETRY_MAX_RETRIES", 2)))
        base_delay = _env_float("DATABASE_RETRY_DELAY_SECONDS", _env_float("RETRY_BASE_DELAY_SECONDS", 0.05))
    elif domain == "ats":
        max_retries = max(0, _env_int("ATS_MAX_RETRIES", _env_int("RETRY_MAX_RETRIES", 2)))
        base_delay = _env_float("ATS_RETRY_BASE_DELAY_SECONDS", _env_float("RETRY_BASE_DELAY_SECONDS", 0.4))
    else:
        max_retries = max(0, _env_int("ORCHESTRATION_MAX_RETRIES", _env_int("RETRY_MAX_RETRIES", 2)))
        base_delay = _env_float("ORCHESTRATION_RETRY_BASE_DELAY_SECONDS", _env_float("RETRY_BASE_DELAY_SECONDS", 0.4))

    return RetryPolicy(
        domain=domain,
        max_retries=max_retries,
        base_delay_seconds=max(0.0, base_delay),
        max_delay_seconds=max(0.0, _env_float("RETRY_MAX_DELAY_SECONDS", 3.0)),
        backoff_multiplier=max(1.0, _env_float("RETRY_BACKOFF_MULTIPLIER", 2.0)),
    )


def retry_delay(policy: RetryPolicy, retry_count: int) -> float:
    if retry_count <= 0 or policy.base_delay_seconds <= 0:
        return 0.0
    delay = policy.base_delay_seconds * (policy.backoff_multiplier ** max(0, retry_count - 1))
    return round(min(delay, policy.max_delay_seconds), 3)


def retry_decision(
    *,
    domain: RetryDomain = "workflow",
    retry_count: int = 0,
    error: str | None = None,
    policy: RetryPolicy | None = None,
) -> RetryDecision:
    runtime_policy = policy or retry_policy(domain)
    next_retry_count = retry_count + 1
    should_retry = bool(error) and retry_count < runtime_policy.max_retries
    return RetryDecision(
        domain=runtime_policy.domain,
        attempt=next_retry_count,
        max_attempts=runtime_policy.max_attempts,
        retry_count=retry_count,
        max_retries=runtime_policy.max_retries,
        should_retry=should_retry,
        delay_seconds=retry_delay(runtime_policy, next_retry_count) if should_retry else 0.0,
        reason="Retry budget remains." if should_retry else "Retry budget exhausted or no error.",
    )


def retry_diagnostics() -> dict[str, Any]:
    return {
        "workflow": retry_policy("workflow").as_dict(),
        "llm": retry_policy("llm").as_dict(),
        "ats": retry_policy("ats").as_dict(),
        "persistence": retry_policy("persistence").as_dict(),
        "deterministic_backoff": True,
    }


__all__ = [
    "RetryDecision",
    "RetryDomain",
    "RetryPolicy",
    "retry_decision",
    "retry_delay",
    "retry_diagnostics",
    "retry_policy",
]
