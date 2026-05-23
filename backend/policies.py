from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from typing import Any, Literal

from backend.retry import RetryPolicy, retry_decision, retry_policy


PolicyAction = Literal["continue", "retry", "monitor", "degrade", "escalate"]


@dataclass(frozen=True)
class ExecutionPolicy:
    max_retries: int = 2
    confidence_floor: float = 0.55
    enable_fallback_model: bool = True
    enable_investigation: bool = True
    max_result_rows: int = 500

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


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


def default_execution_policy() -> ExecutionPolicy:
    workflow_retry = retry_policy("workflow")
    return ExecutionPolicy(
        max_retries=workflow_retry.max_retries,
        confidence_floor=min(1.0, max(0.0, _env_float("ORCHESTRATION_CONFIDENCE_FLOOR", 0.55))),
        enable_fallback_model=_env_bool("ORCHESTRATION_ENABLE_FALLBACK_MODEL", True),
        enable_investigation=_env_bool("ORCHESTRATION_ENABLE_INVESTIGATION", True),
        max_result_rows=max(1, _env_int("ORCHESTRATION_MAX_RESULT_ROWS", 500)),
    )


def evaluate_stage_policy(
    *,
    stage: str,
    confidence: float,
    retry_count: int = 0,
    error: str | None = None,
    policy: ExecutionPolicy | None = None,
    retry: RetryPolicy | None = None,
) -> dict[str, Any]:
    runtime_policy = policy or default_execution_policy()
    retry_runtime = retry or retry_policy("workflow")
    retry_status = retry_decision(domain="workflow", retry_count=retry_count, error=error, policy=retry_runtime)
    action: PolicyAction = "continue"
    reason = "Stage is within configured runtime policy."

    if retry_status.should_retry:
        action = "retry"
        reason = "Stage failed and retry budget remains."
    elif error:
        action = "degrade"
        reason = "Stage failed after retry budget was exhausted."
    elif confidence < runtime_policy.confidence_floor:
        action = "monitor"
        reason = "Stage confidence is below the configured floor."

    if action == "degrade" and stage in {"validation", "execution"}:
        action = "escalate"
        reason = "Critical workflow stage failed and requires investigation review."

    return {
        "stage": stage,
        "action": action,
        "reason": reason,
        "confidence": round(confidence, 3),
        "retry_count": retry_count,
        "max_retries": runtime_policy.max_retries,
        "retry": retry_status.as_dict(),
        "confidence_floor": runtime_policy.confidence_floor,
    }


__all__ = ["ExecutionPolicy", "default_execution_policy", "evaluate_stage_policy"]
