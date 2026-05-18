from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from backend.models import DEFAULT_ORGANIZATION_ID, DEFAULT_USER_ID, DEFAULT_WORKSPACE_ID, UsageEventType, UsageRecord
from backend.storage import SQLiteUsageStorage, UsageStorage


@dataclass
class UsageService:
    usage_storage: UsageStorage

    def record(
        self,
        event_type: UsageEventType,
        *,
        organization_id: str = DEFAULT_ORGANIZATION_ID,
        workspace_id: str = DEFAULT_WORKSPACE_ID,
        user_id: str = DEFAULT_USER_ID,
        quantity: float = 1.0,
        estimated_cost_usd: float = 0.0,
        metadata: dict[str, object] | None = None,
    ) -> UsageRecord:
        usage = UsageRecord(
            usage_id=f"usage:{uuid4()}",
            organization_id=organization_id,
            workspace_id=workspace_id,
            user_id=user_id,
            event_type=event_type,
            quantity=quantity,
            estimated_cost_usd=estimated_cost_usd,
            timestamp=datetime.now(timezone.utc).isoformat(),
            metadata=metadata or {},
        )
        self.usage_storage.append(usage)
        return usage

    def list_usage(
        self,
        *,
        organization_id: str | None = None,
        workspace_id: str | None = None,
    ) -> tuple[UsageRecord, ...]:
        return self.usage_storage.list(organization_id=organization_id, workspace_id=workspace_id)


usage_service = UsageService(usage_storage=SQLiteUsageStorage())


__all__ = ["UsageService", "usage_service"]
