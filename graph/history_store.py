"""Scoped SQL examples; legacy unscoped Chroma data is intentionally never read.

Questions stay in the configured database and use local lexical embeddings.
Every call must name the authenticated organization, workspace and connector.
"""
from __future__ import annotations

import logging
from typing import Any

from backend.memory import MemoryDocument, build_vector_memory_store


logger = logging.getLogger(__name__)


def _has_scope(organization_id, workspace_id, connector_id) -> bool:
    return all(isinstance(value, str) and value.strip() for value in (organization_id, workspace_id, connector_id))


def save_query_to_history(
    question: str, sql: str, success: bool = True, *, organization_id: str | None = None,
    workspace_id: str | None = None, connector_id: str | None = None,
) -> bool:
    """Persist a successful example only when complete scope is provided."""
    if not success or not _has_scope(organization_id, workspace_id, connector_id):
        return False
    try:
        build_vector_memory_store().upsert(MemoryDocument(
            namespace="sql_query", text=question, organization_id=organization_id,
            workspace_id=workspace_id, connector_id=connector_id, metadata={"sql": sql},
        ))
        return True
    except Exception as exc:
        # Do not log SQL, customer text, connection strings, or credentials.
        logger.warning("Scoped query history write unavailable (%s).", type(exc).__name__)
        return False


def retrieve_similar_queries(
    question: str, top_k: int = 3, *, organization_id: str | None = None,
    workspace_id: str | None = None, connector_id: str | None = None,
) -> list[dict[str, Any]]:
    if not _has_scope(organization_id, workspace_id, connector_id):
        return []
    try:
        records = build_vector_memory_store().search(
            question, top_k=top_k, namespace="sql_query", organization_id=organization_id,
            workspace_id=workspace_id, connector_id=connector_id,
        )
        return [{"question": item.text, "sql": item.metadata.get("sql", "")} for item in records]
    except Exception as exc:
        logger.warning("Scoped query history retrieval unavailable (%s).", type(exc).__name__)
        return []


def get_history_count(
    *, organization_id: str | None = None, workspace_id: str | None = None, connector_id: str | None = None,
) -> int:
    if not _has_scope(organization_id, workspace_id, connector_id):
        return 0
    return build_vector_memory_store().count(
        organization_id=organization_id, workspace_id=workspace_id, namespace="sql_query", connector_id=connector_id,
    )


def delete_scope(*, organization_id: str, workspace_id: str) -> int:
    """Delete all SQL examples in one workspace; persistence failures propagate."""
    return build_vector_memory_store().delete_workspace(
        organization_id=organization_id, workspace_id=workspace_id, namespace="sql_query",
    )


def clear_history(*, organization_id: str, workspace_id: str) -> int:
    return delete_scope(organization_id=organization_id, workspace_id=workspace_id)
