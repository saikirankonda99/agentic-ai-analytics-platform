"""Workspace-scoped, durable memory with local deterministic embeddings.

The default store lives in the platform database. VECTOR_DATABASE_URL selects
PostgreSQL/pgvector; the extension must be installed by the database operator.
No embedding provider receives workspace text.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Literal, Protocol

from backend.config import settings
from backend.models import DEFAULT_ORGANIZATION_ID, DEFAULT_WORKSPACE_ID


MemoryNamespace = Literal[
    "semantic_dataset_summary", "investigation", "executive_insight", "workflow_context", "sql_query",
]
_NAMESPACES = {"semantic_dataset_summary", "investigation", "executive_insight", "workflow_context", "sql_query"}


@dataclass(frozen=True)
class MemoryDocument:
    namespace: MemoryNamespace
    text: str
    organization_id: str = DEFAULT_ORGANIZATION_ID
    workspace_id: str = DEFAULT_WORKSPACE_ID
    metadata: dict[str, Any] = field(default_factory=dict)
    connector_id: str = ""


@dataclass(frozen=True)
class MemoryRecord:
    memory_id: str
    organization_id: str
    workspace_id: str
    namespace: MemoryNamespace
    text: str
    embedding: tuple[float, ...]
    metadata: dict[str, Any] = field(default_factory=dict)
    connector_id: str = ""


@dataclass(frozen=True)
class MemorySearchResult:
    memory_id: str
    organization_id: str
    workspace_id: str
    namespace: MemoryNamespace
    text: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)
    connector_id: str = ""


class EmbeddingService(Protocol):
    def embed(self, text: str) -> tuple[float, ...]:
        """Generate an embedding vector for text."""


class VectorMemoryStore(Protocol):
    def upsert(self, document: MemoryDocument) -> MemoryRecord: ...

    def search(
        self, query: str, *, organization_id: str = DEFAULT_ORGANIZATION_ID,
        workspace_id: str = DEFAULT_WORKSPACE_ID, namespace: MemoryNamespace | None = None,
        connector_id: str | None = None, top_k: int = 5,
    ) -> tuple[MemorySearchResult, ...]: ...

    def delete_workspace(
        self, *, organization_id: str, workspace_id: str, namespace: MemoryNamespace | None = None,
    ) -> int: ...

    def count(
        self, *, organization_id: str, workspace_id: str, namespace: MemoryNamespace | None = None,
        connector_id: str | None = None,
    ) -> int: ...

    def prune_before(self, cutoff: str) -> int: ...


class HashingEmbeddingService:
    """Stable lexical embeddings, reproducible across processes and restarts."""

    def __init__(self, dimensions: int = 64) -> None:
        if not isinstance(dimensions, int) or not 1 <= dimensions <= 2000:
            raise ValueError("Embedding dimensions must be between 1 and 2000.")
        self.dimensions = dimensions

    def embed(self, text: str) -> tuple[float, ...]:
        vector = [0.0] * self.dimensions
        for token in re.findall(r"\w+", text.casefold()):
            index = int.from_bytes(hashlib.sha256(token.encode()).digest()[:8], "big") % self.dimensions
            vector[index] += 1.0
        magnitude = math.sqrt(sum(value * value for value in vector))
        if not magnitude:
            vector[0] = magnitude = 1.0
        return tuple(value / magnitude for value in vector)


def _scope(organization_id: str, workspace_id: str) -> None:
    if not isinstance(organization_id, str) or not organization_id.strip():
        raise ValueError("Memory requires an explicit organization ID.")
    if not isinstance(workspace_id, str) or not workspace_id.strip():
        raise ValueError("Memory requires an explicit workspace ID.")


def _record(document: MemoryDocument, embedding_service: EmbeddingService) -> MemoryRecord:
    _scope(document.organization_id, document.workspace_id)
    if document.namespace not in _NAMESPACES:
        raise ValueError("Unknown memory namespace.")
    if document.namespace == "sql_query" and not document.connector_id:
        raise ValueError("SQL memory requires connector provenance.")
    if not isinstance(document.text, str) or not document.text.strip():
        raise ValueError("Memory text cannot be empty.")
    identity = json.dumps([
        document.organization_id, document.workspace_id, document.namespace, document.connector_id, document.text,
    ], separators=(",", ":"))
    return MemoryRecord(
        memory_id="memory:" + hashlib.sha256(identity.encode()).hexdigest(),
        organization_id=document.organization_id, workspace_id=document.workspace_id,
        namespace=document.namespace, text=document.text, embedding=embedding_service.embed(document.text),
        metadata=dict(document.metadata), connector_id=document.connector_id,
    )


def _limit(top_k: int) -> int:
    if not isinstance(top_k, int) or isinstance(top_k, bool) or not 1 <= top_k <= 100:
        raise ValueError("top_k must be between 1 and 100.")
    return top_k


def _result(record: MemoryRecord, score: float) -> MemorySearchResult:
    return MemorySearchResult(
        memory_id=record.memory_id, organization_id=record.organization_id, workspace_id=record.workspace_id,
        namespace=record.namespace, text=record.text, score=score, metadata=record.metadata,
        connector_id=record.connector_id,
    )


class InMemoryVectorMemoryStore:
    """Explicit ephemeral implementation for tests and callers that choose it."""

    def __init__(self, embedding_service: EmbeddingService | None = None) -> None:
        self.embedding_service = embedding_service or HashingEmbeddingService()
        self._records: dict[str, MemoryRecord] = {}
        self._updated_at: dict[str, str] = {}

    def upsert(self, document: MemoryDocument) -> MemoryRecord:
        record = _record(document, self.embedding_service)
        self._records[record.memory_id] = record
        self._updated_at[record.memory_id] = datetime.now(timezone.utc).isoformat()
        return record

    def search(
        self, query: str, *, organization_id: str = DEFAULT_ORGANIZATION_ID,
        workspace_id: str = DEFAULT_WORKSPACE_ID, namespace: MemoryNamespace | None = None,
        connector_id: str | None = None, top_k: int = 5,
    ) -> tuple[MemorySearchResult, ...]:
        _scope(organization_id, workspace_id)
        _limit(top_k)
        embedding = self.embedding_service.embed(query)
        results = [
            _result(record, _cosine_similarity(embedding, record.embedding))
            for record in self._records.values()
            if record.organization_id == organization_id and record.workspace_id == workspace_id
            and (namespace is None or record.namespace == namespace)
            and (connector_id is None or record.connector_id == connector_id)
        ]
        return tuple(sorted(results, key=lambda item: (-item.score, item.memory_id))[:top_k])

    def delete_workspace(
        self, *, organization_id: str, workspace_id: str, namespace: MemoryNamespace | None = None,
    ) -> int:
        _scope(organization_id, workspace_id)
        ids = [key for key, value in self._records.items()
               if value.organization_id == organization_id and value.workspace_id == workspace_id
               and (namespace is None or value.namespace == namespace)]
        for key in ids:
            del self._records[key]
            self._updated_at.pop(key, None)
        return len(ids)

    def prune_before(self, cutoff: str) -> int:
        cutoff = _utc_cutoff(cutoff)
        ids = [key for key, updated_at in self._updated_at.items() if updated_at < cutoff]
        for key in ids:
            self._records.pop(key, None)
            self._updated_at.pop(key, None)
        return len(ids)

    def count(self, *, organization_id: str, workspace_id: str, namespace=None, connector_id=None) -> int:
        _scope(organization_id, workspace_id)
        return sum(1 for item in self._records.values()
                   if item.organization_id == organization_id and item.workspace_id == workspace_id
                   and (namespace is None or item.namespace == namespace)
                   and (connector_id is None or item.connector_id == connector_id))


class RelationalVectorMemoryStore:
    """Durable SQLite/standard PostgreSQL memory, with tenant filtering in SQL."""

    table_name = "analytics_memory"
    vector_type = "TEXT"
    postgres_vector = False

    def __init__(self, database_url: str, embedding_service: EmbeddingService | None = None) -> None:
        if not database_url.startswith(("sqlite:///", "postgresql://", "postgres://")):
            raise ValueError("Unsupported memory database URL.")
        if database_url.startswith("sqlite:///") and not database_url.removeprefix("sqlite:///").strip():
            raise ValueError("Memory SQLite database URL requires a file path.")
        self.database_url = database_url
        self.is_postgres = not database_url.startswith("sqlite:///")
        self.embedding_service = embedding_service or HashingEmbeddingService()
        self.dimensions = len(self.embedding_service.embed("dimensions"))
        self.embedding_version = f"{type(self.embedding_service).__name__}-sha256-v1:{self.dimensions}"
        self._initialized = False

    @contextmanager
    def _connect(self) -> Iterator[Any]:
        if self.is_postgres:
            import psycopg
            from psycopg.rows import dict_row
            with psycopg.connect(self.database_url, row_factory=dict_row, connect_timeout=5) as connection:
                self._initialize(connection)
                yield connection
        else:
            path = Path(self.database_url.removeprefix("sqlite:///"))
            path.parent.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(path, timeout=10)
            connection.row_factory = sqlite3.Row
            try:
                self._initialize(connection)
                yield connection
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            finally:
                connection.close()

    def _execute(self, connection, sql, params=()):
        return connection.execute(sql.replace("?", "%s") if self.is_postgres else sql, params)

    def _initialize(self, connection) -> None:
        if self._initialized:
            return
        if self.is_postgres:
            # Platform, workflow and queue bootstraps use the same transaction
            # lock: concurrent first boots cannot race PostgreSQL catalog DDL.
            connection.execute("SELECT pg_advisory_xact_lock(%s)", (846231905,))
        if self.postgres_vector:
            row = connection.execute("SELECT 1 FROM pg_extension WHERE extname = 'vector'").fetchone()
            if row is None:
                raise RuntimeError("VECTOR_DATABASE_URL requires the pgvector extension installed by a database administrator.")
        vector_type = f"vector({self.dimensions})" if self.postgres_vector else "TEXT"
        self._execute(connection, f"""
            CREATE TABLE IF NOT EXISTS {self.table_name} (
                memory_id TEXT PRIMARY KEY, organization_id TEXT NOT NULL,
                workspace_id TEXT NOT NULL, namespace TEXT NOT NULL, connector_id TEXT NOT NULL,
                content TEXT NOT NULL, embedding {vector_type} NOT NULL,
                embedding_version TEXT NOT NULL, metadata_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        self._execute(connection, f"""
            CREATE INDEX IF NOT EXISTS idx_{self.table_name}_scope
            ON {self.table_name}(organization_id, workspace_id, namespace, connector_id)
        """)
        # The DDL is committed separately so a later operation rollback cannot
        # leave this instance believing its table exists when it does not.
        connection.commit()
        self._initialized = True

    def upsert(self, document: MemoryDocument) -> MemoryRecord:
        record = _record(document, self.embedding_service)
        if len(record.embedding) != self.dimensions or not all(math.isfinite(item) for item in record.embedding):
            raise ValueError("Embedding dimensions or values are invalid.")
        embedding_placeholder = "?::vector" if self.postgres_vector else "?"
        with self._connect() as connection:
            self._execute(connection, f"""
                INSERT INTO {self.table_name}
                (memory_id, organization_id, workspace_id, namespace, connector_id, content,
                 embedding, embedding_version, metadata_json, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, {embedding_placeholder}, ?, ?, ?)
                ON CONFLICT(memory_id) DO UPDATE SET
                    embedding = excluded.embedding, embedding_version = excluded.embedding_version,
                    metadata_json = excluded.metadata_json, updated_at = excluded.updated_at
            """, (record.memory_id, record.organization_id, record.workspace_id, record.namespace,
                  record.connector_id, record.text, json.dumps(record.embedding), self.embedding_version,
                  json.dumps(record.metadata, sort_keys=True), datetime.now(timezone.utc).isoformat()))
        return record

    def _where(self, organization_id, workspace_id, namespace=None, connector_id=None):
        _scope(organization_id, workspace_id)
        terms = ["organization_id = ?", "workspace_id = ?"]
        params = [organization_id, workspace_id]
        if namespace is not None:
            if namespace not in _NAMESPACES:
                raise ValueError("Unknown memory namespace.")
            terms.append("namespace = ?")
            params.append(namespace)
        if connector_id is not None:
            terms.append("connector_id = ?")
            params.append(connector_id)
        return " AND ".join(terms), params

    def search(
        self, query: str, *, organization_id: str = DEFAULT_ORGANIZATION_ID,
        workspace_id: str = DEFAULT_WORKSPACE_ID, namespace: MemoryNamespace | None = None,
        connector_id: str | None = None, top_k: int = 5,
    ) -> tuple[MemorySearchResult, ...]:
        _limit(top_k)
        where, params = self._where(organization_id, workspace_id, namespace, connector_id)
        embedding = self.embedding_service.embed(query)
        with self._connect() as connection:
            if self.postgres_vector:
                rows = self._execute(connection, f"""
                    SELECT *, 1 - (embedding <=> ?::vector) AS similarity
                    FROM {self.table_name} WHERE {where} AND embedding_version = ?
                    ORDER BY embedding <=> ?::vector, memory_id LIMIT ?
                """, [json.dumps(embedding), *params, self.embedding_version, json.dumps(embedding), top_k]).fetchall()
                return tuple(self._search_result(row, float(row["similarity"])) for row in rows)
            # Filtering happens before candidate loading. The lexical fallback
            # scores the 2,000 most recently updated records in this exact scope.
            rows = self._execute(connection, f"""
                SELECT * FROM {self.table_name} WHERE {where} AND embedding_version = ?
                ORDER BY updated_at DESC, memory_id LIMIT 2000
            """, [*params, self.embedding_version]).fetchall()
        results = [self._search_result(row, _cosine_similarity(embedding, tuple(json.loads(row["embedding"]))))
                   for row in rows]
        return tuple(sorted(results, key=lambda item: (-item.score, item.memory_id))[:top_k])

    def _search_result(self, row, score) -> MemorySearchResult:
        return MemorySearchResult(
            memory_id=row["memory_id"], organization_id=row["organization_id"], workspace_id=row["workspace_id"],
            namespace=row["namespace"], text=row["content"], score=score,
            metadata=json.loads(row["metadata_json"]), connector_id=row["connector_id"],
        )

    def count(self, *, organization_id: str, workspace_id: str, namespace=None, connector_id=None) -> int:
        where, params = self._where(organization_id, workspace_id, namespace, connector_id)
        with self._connect() as connection:
            row = self._execute(connection, f"SELECT COUNT(*) AS count FROM {self.table_name} WHERE {where}", params).fetchone()
        return int(row["count"])

    def delete_workspace(
        self, *, organization_id: str, workspace_id: str, namespace: MemoryNamespace | None = None,
    ) -> int:
        where, params = self._where(organization_id, workspace_id, namespace)
        with self._connect() as connection:
            result = self._execute(connection, f"DELETE FROM {self.table_name} WHERE {where}", params)
            return result.rowcount

    def prune_before(self, cutoff: str) -> int:
        """Operator retention operation; customer-facing deletion remains scoped."""
        cutoff = _utc_cutoff(cutoff)
        with self._connect() as connection:
            result = self._execute(connection, f"DELETE FROM {self.table_name} WHERE updated_at < ?", (cutoff,))
            return result.rowcount


class PgVectorMemoryStore(RelationalVectorMemoryStore):
    table_name = "analytics_vector_memory"
    postgres_vector = True

    def __init__(self, database_url: str, embedding_service: EmbeddingService | None = None) -> None:
        if not database_url.startswith(("postgresql://", "postgres://")):
            raise ValueError("pgvector requires a PostgreSQL database URL.")
        super().__init__(database_url, embedding_service)


def build_vector_memory_store() -> VectorMemoryStore:
    vector_url = os.getenv("VECTOR_DATABASE_URL") or settings.vector_database_url
    if vector_url:
        return PgVectorMemoryStore(vector_url)
    database_url = os.getenv("DATABASE_URL") or os.getenv("PLATFORM_DATABASE_URL") or settings.database_url
    return RelationalVectorMemoryStore(database_url)


def _cosine_similarity(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    if len(left) != len(right):
        raise ValueError("Embedding dimensions do not match.")
    return sum(a * b for a, b in zip(left, right))


def _utc_cutoff(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError
        return parsed.astimezone(timezone.utc).isoformat()
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError("Retention cutoff must be an ISO timestamp with a timezone.") from exc


__all__ = [
    "EmbeddingService", "HashingEmbeddingService", "InMemoryVectorMemoryStore", "MemoryDocument", "MemoryNamespace",
    "MemoryRecord", "MemorySearchResult", "PgVectorMemoryStore", "RelationalVectorMemoryStore",
    "VectorMemoryStore", "build_vector_memory_store",
]
