from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal


SensitivityLevel = Literal["public", "internal", "confidential", "restricted"]
ApprovalState = Literal["approved", "review_required", "blocked"]
RetentionClass = Literal["short", "standard", "extended"]


@dataclass(frozen=True)
class DatasetMetadata:
    dataset_id: str
    name: str
    owner: str
    domain: str
    sensitivity: SensitivityLevel
    tags: tuple[str, ...] = ()
    source: str = "sqlite"
    freshness_minutes: int | None = None
    schema_version: str = "v1"
    approval_state: ApprovalState = "review_required"
    retention_class: RetentionClass = "standard"
    audit: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["tags"] = list(self.tags)
        payload["trust_score"] = dataset_trust_score(self)
        payload["governance_status"] = governance_status(payload["trust_score"], self.approval_state)
        return payload


@dataclass(frozen=True)
class WorkspacePolicy:
    workspace_id: str
    allow_restricted_data: bool = False
    require_approval_for_confidential: bool = True
    telemetry_retention_days: int = 30
    investigation_retention_days: int = 90
    connector_access: dict[str, tuple[SensitivityLevel, ...]] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["connector_access"] = {key: list(value) for key, value in self.connector_access.items()}
        return payload


def default_dataset_registry() -> list[DatasetMetadata]:
    timestamp = datetime.now(timezone.utc).isoformat()
    return [
        DatasetMetadata(
            dataset_id="dataset:chinook-customers",
            name="Customer Account Analytics",
            owner="Revenue Operations",
            domain="customer",
            sensitivity="confidential",
            tags=("pii", "customer", "revenue"),
            freshness_minutes=60,
            approval_state="approved",
            audit={"registered_at": timestamp, "classification_source": "schema_profile"},
        ),
        DatasetMetadata(
            dataset_id="dataset:chinook-invoices",
            name="Invoice Revenue Ledger",
            owner="Finance Analytics",
            domain="finance",
            sensitivity="internal",
            tags=("revenue", "billing", "finance"),
            freshness_minutes=30,
            approval_state="approved",
            audit={"registered_at": timestamp, "classification_source": "schema_profile"},
        ),
        DatasetMetadata(
            dataset_id="dataset:chinook-tracks",
            name="Catalog Usage Metadata",
            owner="Product Analytics",
            domain="product",
            sensitivity="internal",
            tags=("catalog", "usage", "product"),
            freshness_minutes=240,
            approval_state="review_required",
            audit={"registered_at": timestamp, "classification_source": "schema_profile"},
        ),
    ]


def default_workspace_policy(workspace_id: str) -> WorkspacePolicy:
    return WorkspacePolicy(
        workspace_id=workspace_id,
        connector_access={
            "sqlite": ("public", "internal", "confidential"),
            "warehouse": ("public", "internal"),
        },
    )


def dataset_trust_score(dataset: DatasetMetadata) -> float:
    score = 0.42
    if dataset.owner:
        score += 0.14
    if dataset.tags:
        score += min(len(dataset.tags), 4) * 0.05
    if dataset.freshness_minutes is not None:
        score += 0.12 if dataset.freshness_minutes <= 120 else 0.06
    if dataset.approval_state == "approved":
        score += 0.15
    if dataset.sensitivity in {"confidential", "restricted"}:
        score -= 0.04
    return round(max(0.0, min(score, 0.99)), 2)


def governance_status(trust_score: float, approval_state: ApprovalState) -> str:
    if approval_state == "blocked":
        return "blocked"
    if approval_state == "review_required" or trust_score < 0.7:
        return "review_required"
    return "trusted"


def validate_dataset_access(dataset: DatasetMetadata, policy: WorkspacePolicy, connector: str = "sqlite") -> dict[str, Any]:
    allowed_levels = policy.connector_access.get(connector, ())
    allowed = dataset.sensitivity in allowed_levels
    reason = "Dataset sensitivity is allowed for this connector policy."
    if dataset.sensitivity == "restricted" and not policy.allow_restricted_data:
        allowed = False
        reason = "Restricted datasets require explicit workspace approval."
    elif dataset.sensitivity == "confidential" and policy.require_approval_for_confidential and dataset.approval_state != "approved":
        allowed = False
        reason = "Confidential datasets must be approved before orchestration."
    elif not allowed:
        reason = "Connector policy does not permit this sensitivity level."
    return {
        "dataset_id": dataset.dataset_id,
        "connector": connector,
        "allowed": allowed,
        "approval_state": dataset.approval_state,
        "sensitivity": dataset.sensitivity,
        "reason": reason,
    }


def governance_overview(
    workspace_id: str,
    datasets: list[DatasetMetadata] | None = None,
    policy: WorkspacePolicy | None = None,
) -> dict[str, Any]:
    datasets = datasets or default_dataset_registry()
    policy = policy or default_workspace_policy(workspace_id)
    dataset_rows = [dataset.as_dict() for dataset in datasets]
    trusted = [item for item in dataset_rows if item["governance_status"] == "trusted"]
    review_required = [item for item in dataset_rows if item["governance_status"] == "review_required"]
    blocked = [item for item in dataset_rows if item["governance_status"] == "blocked"]
    access = [validate_dataset_access(dataset, policy) for dataset in datasets]
    return {
        "workspace_id": workspace_id,
        "policy": policy.as_dict(),
        "datasets": dataset_rows,
        "summary": {
            "dataset_count": len(dataset_rows),
            "trusted_count": len(trusted),
            "review_required_count": len(review_required),
            "blocked_count": len(blocked),
            "average_trust_score": round(sum(item["trust_score"] for item in dataset_rows) / len(dataset_rows), 2)
            if dataset_rows
            else 0.0,
            "sensitivity_counts": {
                level: len([item for item in dataset_rows if item["sensitivity"] == level])
                for level in ("public", "internal", "confidential", "restricted")
            },
        },
        "access_evaluations": access,
        "audit_metadata": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "compliance_ready": not blocked,
            "retention": {
                "telemetry_days": policy.telemetry_retention_days,
                "investigation_days": policy.investigation_retention_days,
            },
        },
    }


__all__ = [
    "DatasetMetadata",
    "WorkspacePolicy",
    "dataset_trust_score",
    "default_dataset_registry",
    "default_workspace_policy",
    "governance_overview",
    "validate_dataset_access",
]
