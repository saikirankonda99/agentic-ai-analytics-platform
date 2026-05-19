from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


TELEMETRY_SCHEMA_VERSION = "2026-05-analytics-v1"
RUNTIME_EVENT_TYPES = (
    "workflow_event",
    "lifecycle_transition",
    "stage_transition",
    "agent_update",
    "telemetry_update",
    "investigation_update",
    "openai_request",
    "recovery_update",
)
FAILURE_CATEGORIES = {
    "connection": ("APIConnectionError", "ConnectError", "ReadError", "network", "proxy"),
    "timeout": ("APITimeoutError", "TimeoutException", "timeout"),
    "provider_status": ("APIStatusError", "rate_limit", "server_error", "status"),
    "validation": ("validation", "unsafe", "blocked"),
    "execution": ("sqlite", "sql execution", "database"),
}


@dataclass(frozen=True)
class TelemetryEvent:
    event_id: str
    correlation_id: str
    workflow_id: str
    phase: str
    status: str
    message: str
    timestamp: str
    latency_ms: int = 0
    model: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    retry_count: int = 0
    error_type: str | None = None
    error_message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


def new_correlation_id(prefix: str = "wf") -> str:
    return f"{prefix}-{uuid4().hex[:12]}"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def telemetry_event(
    *,
    correlation_id: str,
    workflow_id: str,
    phase: str,
    status: str,
    message: str,
    step: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    step = step or {}
    event = TelemetryEvent(
        event_id=f"evt-{uuid4().hex[:12]}",
        correlation_id=correlation_id,
        workflow_id=workflow_id,
        phase=phase,
        status=status,
        message=message,
        timestamp=utc_now(),
        latency_ms=int(step.get("latency_ms", 0) or 0),
        model=step.get("model", "") or "",
        prompt_tokens=int(step.get("prompt_tokens", 0) or 0),
        completion_tokens=int(step.get("completion_tokens", 0) or 0),
        total_tokens=int(step.get("total_tokens", 0) or 0),
        cost_usd=float(step.get("cost_usd", 0.0) or 0.0),
        retry_count=int(step.get("retries", 0) or step.get("retry_count", 0) or 0),
        error_type=step.get("error_type"),
        error_message=step.get("error_message"),
        metadata=metadata or {},
    )
    return asdict(event)


def validate_telemetry_payload(telemetry: dict[str, Any] | None) -> dict[str, Any]:
    telemetry = dict(telemetry or {})
    steps = []
    for item in telemetry.get("steps", []):
        if not isinstance(item, dict):
            continue
        steps.append(
            {
                **item,
                "prompt_tokens": int(item.get("prompt_tokens", 0) or 0),
                "completion_tokens": int(item.get("completion_tokens", 0) or 0),
                "total_tokens": int(item.get("total_tokens", 0) or 0),
                "cost_usd": float(item.get("cost_usd", 0.0) or 0.0),
                "latency_ms": int(item.get("latency_ms", 0) or 0),
                "usage_available": bool(item.get("usage_available", False)),
            }
        )
    latest_error = next((item for item in reversed(steps) if item.get("error_type") or item.get("error_message")), {})
    telemetry.update(
        {
            "schema_version": telemetry.get("schema_version") or TELEMETRY_SCHEMA_VERSION,
            "correlation_id": telemetry.get("correlation_id") or new_correlation_id(),
            "steps": steps,
            "prompt_tokens": sum(item.get("prompt_tokens", 0) for item in steps),
            "completion_tokens": sum(item.get("completion_tokens", 0) for item in steps),
            "total_tokens": sum(item.get("total_tokens", 0) for item in steps),
            "cost_usd": sum(item.get("cost_usd", 0.0) for item in steps),
            "latency_ms": sum(item.get("latency_ms", 0) for item in steps),
            "model": next((item.get("model", "") for item in reversed(steps) if item.get("model")), telemetry.get("model", "")),
            "usage_available": any(item.get("usage_available", False) for item in steps),
            "error_type": latest_error.get("error_type"),
            "error_message": latest_error.get("error_message"),
            "error_details": latest_error.get("error_details"),
        }
    )
    return telemetry


def phase_latency_breakdown(telemetry: dict[str, Any] | None) -> list[dict[str, Any]]:
    telemetry = validate_telemetry_payload(telemetry)
    return [
        {
            "phase": item.get("step", "unknown"),
            "latency_ms": item.get("latency_ms", 0),
            "model": item.get("model", ""),
            "tokens": item.get("total_tokens", 0),
            "cost_usd": item.get("cost_usd", 0.0),
            "status": "error" if item.get("error_type") else "completed",
        }
        for item in telemetry.get("steps", [])
    ]


def telemetry_export_rows(telemetry: dict[str, Any] | None, trace: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    telemetry = validate_telemetry_payload(telemetry)
    trace_by_step = {item.get("step"): item for item in trace or []}
    rows = []
    for item in telemetry.get("steps", []):
        trace_item = trace_by_step.get(item.get("step"), {})
        rows.append(
            {
                "correlation_id": telemetry.get("correlation_id"),
                "schema_version": telemetry.get("schema_version"),
                "step": item.get("step", ""),
                "status": trace_item.get("status", "unknown"),
                "detail": trace_item.get("detail", ""),
                "model": item.get("model", ""),
                "prompt_tokens": item.get("prompt_tokens", 0),
                "completion_tokens": item.get("completion_tokens", 0),
                "total_tokens": item.get("total_tokens", 0),
                "latency_ms": item.get("latency_ms", 0),
                "cost_usd": item.get("cost_usd", 0.0),
                "error_type": item.get("error_type", ""),
                "error_message": item.get("error_message", ""),
            }
        )
    return rows


def filter_telemetry_events(
    events: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None,
    *,
    query: str = "",
    phase: str = "",
    status: str = "",
) -> list[dict[str, Any]]:
    query = query.lower().strip()
    phase = phase.lower().strip()
    status = status.lower().strip()
    filtered = []
    for event in events or []:
        haystack = f"{event.get('phase', '')} {event.get('status', '')} {event.get('message', '')}".lower()
        if query and query not in haystack:
            continue
        if phase and phase != str(event.get("phase", "")).lower():
            continue
        if status and status != str(event.get("status", "")).lower():
            continue
        filtered.append(dict(event))
    return filtered


def categorize_failure(error_type: str | None = None, error_message: str | None = None) -> str:
    text = f"{error_type or ''} {error_message or ''}".lower()
    if not text.strip():
        return "none"
    for category, markers in FAILURE_CATEGORIES.items():
        if any(marker.lower() in text for marker in markers):
            return category
    return "unknown"


def telemetry_aggregate(events: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None) -> dict[str, Any]:
    rows = [dict(event) for event in events or []]
    failures = [event for event in rows if event.get("error_type") or str(event.get("status", "")).lower() in {"failed", "error"}]
    total_latency = sum(int(event.get("latency_ms", 0) or 0) for event in rows)
    total_tokens = sum(int(event.get("total_tokens", 0) or 0) for event in rows)
    total_cost = sum(float(event.get("cost_usd", 0.0) or 0.0) for event in rows)
    by_phase: dict[str, dict[str, Any]] = {}
    by_failure_category: dict[str, int] = {}
    for event in rows:
        phase = str(event.get("phase") or event.get("step") or "unknown")
        phase_row = by_phase.setdefault(
            phase,
            {"phase": phase, "event_count": 0, "latency_ms": 0, "tokens": 0, "cost_usd": 0.0, "failures": 0},
        )
        phase_row["event_count"] += 1
        phase_row["latency_ms"] += int(event.get("latency_ms", 0) or 0)
        phase_row["tokens"] += int(event.get("total_tokens", 0) or 0)
        phase_row["cost_usd"] += float(event.get("cost_usd", 0.0) or 0.0)
        if event in failures:
            phase_row["failures"] += 1
            category = categorize_failure(event.get("error_type"), event.get("error_message") or event.get("message"))
            by_failure_category[category] = by_failure_category.get(category, 0) + 1
    return {
        "event_count": len(rows),
        "failure_count": len(failures),
        "failure_rate": round((len(failures) / len(rows)) * 100, 2) if rows else 0.0,
        "latency_ms": total_latency,
        "total_tokens": total_tokens,
        "cost_usd": round(total_cost, 6),
        "by_phase": list(by_phase.values()),
        "by_failure_category": by_failure_category,
    }
