"""Deterministic retention of saved workspace content, independent of UI activity."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import os
from typing import Any


HISTORY_FIELDS = (
    "query_history", "workflow_runs", "generated_insights", "telemetry_summaries",
    "recent_activity", "collaboration_events", "sessions",
)
SAVED_FIELDS = ("investigations", "bookmarks", "query_bookmarks", "pinned_investigations", "saved_reports")


def retention_days(name: str, default: int) -> int:
    value = int(os.getenv(name, str(default)))
    if not 1 <= value <= 3650:
        raise ValueError(f"{name} must be between 1 and 3650 days.")
    return value


def _timestamp(item: dict[str, Any], now: datetime) -> datetime:
    for name in ("timestamp", "saved_at", "created_at", "started_at", "updated_at", "_retained_at"):
        value = item.get(name)
        if value:
            try:
                parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
                return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)
            except ValueError:
                continue
    # Old records without dates receive a one-time migration date, not a fresh
    # date on every sweep. They expire after the configured retention period.
    item["_retained_at"] = now.isoformat()
    return now


def apply_workspace_retention(
    memory: dict[str, Any], *, now: datetime | None = None,
    history_days: int | None = None, saved_days: int | None = None,
) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    history_days = history_days if history_days is not None else retention_days("HISTORY_RETENTION_DAYS", 30)
    saved_days = saved_days if saved_days is not None else retention_days("SAVED_REPORT_RETENTION_DAYS", 90)
    if history_days < 1 or saved_days < 1:
        raise ValueError("Retention must be at least one day.")
    result = deepcopy(memory)

    def retained(items: Any, days: int) -> list[dict[str, Any]]:
        cutoff = now - timedelta(days=days)
        return [item for item in (items or []) if isinstance(item, dict) and _timestamp(item, now) >= cutoff]

    for field in HISTORY_FIELDS:
        if field in result:
            result[field] = retained(result[field], history_days)
    for field in SAVED_FIELDS:
        if field in result:
            result[field] = retained(result[field], saved_days)
    for session in result.get("sessions", []):
        session["transcripts"] = retained(session.get("transcripts", []), history_days)
        session["workflow_ids"] = list(dict.fromkeys(
            item["workflow_id"] for item in session["transcripts"] if item.get("workflow_id")
        ))
    semantic = result.get("semantic_dataset_memory", {})
    if isinstance(semantic, dict):
        result["semantic_dataset_memory"] = {
            key: value for key, value in semantic.items()
            if isinstance(value, dict) and _timestamp(value, now) >= now - timedelta(days=history_days)
        }
    return result
