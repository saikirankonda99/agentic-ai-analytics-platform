from __future__ import annotations

from dataclasses import dataclass, field
from math import sqrt
from typing import Any, Literal, Protocol
from uuid import uuid4

from backend.models import DEFAULT_WORKSPACE_ID


MemoryNamespace = Literal[
    "semantic_dataset_summary",
    "investigation",
    "executive_insight",
    "workflow_context",
]


@dataclass(frozen=True)
class MemoryDocument:
    namespace: MemoryNamespace
    text: str
    workspace_id: str = DEFAULT_WORKSPACE_ID
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MemoryRecord:
    memory_id: str
    workspace_id: str
    namespace: MemoryNamespace
    text: str
    embedding: tuple[float, ...]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MemorySearchResult:
    memory_id: str
    workspace_id: str
    namespace: MemoryNamespace
    text: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)


class EmbeddingService(Protocol):
    def embed(self, text: str) -> tuple[float, ...]:
        """Generate an embedding vector for text."""


class VectorMemoryStore(Protocol):
    def upsert(self, document: MemoryDocument) -> MemoryRecord:
        """Persist a memory document and its embedding."""

    def search(
        self,
        query: str,
        *,
        workspace_id: str = DEFAULT_WORKSPACE_ID,
        namespace: MemoryNamespace | None = None,
        top_k: int = 5,
    ) -> tuple[MemorySearchResult, ...]:
        """Retrieve semantically similar memory records."""


class HashingEmbeddingService:
    def __init__(self, dimensions: int = 64) -> None:
        self.dimensions = dimensions

    def embed(self, text: str) -> tuple[float, ...]:
        vector = [0.0] * self.dimensions
        for token in text.lower().split():
            vector[hash(token) % self.dimensions] += 1.0
        magnitude = sqrt(sum(value * value for value in vector)) or 1.0
        return tuple(value / magnitude for value in vector)


class InMemoryVectorMemoryStore:
    def __init__(self, embedding_service: EmbeddingService | None = None) -> None:
        self.embedding_service = embedding_service or HashingEmbeddingService()
        self._records: dict[str, MemoryRecord] = {}

    def upsert(self, document: MemoryDocument) -> MemoryRecord:
        record = MemoryRecord(
            memory_id=f"memory:{uuid4()}",
            workspace_id=document.workspace_id,
            namespace=document.namespace,
            text=document.text,
            embedding=self.embedding_service.embed(document.text),
            metadata=document.metadata,
        )
        self._records[record.memory_id] = record
        return record

    def search(
        self,
        query: str,
        *,
        workspace_id: str = DEFAULT_WORKSPACE_ID,
        namespace: MemoryNamespace | None = None,
        top_k: int = 5,
    ) -> tuple[MemorySearchResult, ...]:
        query_embedding = self.embedding_service.embed(query)
        candidates = [
            record
            for record in self._records.values()
            if record.workspace_id == workspace_id and (namespace is None or record.namespace == namespace)
        ]
        results = [
            MemorySearchResult(
                memory_id=record.memory_id,
                workspace_id=record.workspace_id,
                namespace=record.namespace,
                text=record.text,
                score=_cosine_similarity(query_embedding, record.embedding),
                metadata=record.metadata,
            )
            for record in candidates
        ]
        return tuple(sorted(results, key=lambda result: result.score, reverse=True)[:top_k])


def _cosine_similarity(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    return sum(left_value * right_value for left_value, right_value in zip(left, right))


__all__ = [
    "EmbeddingService",
    "HashingEmbeddingService",
    "InMemoryVectorMemoryStore",
    "MemoryDocument",
    "MemoryNamespace",
    "MemoryRecord",
    "MemorySearchResult",
    "VectorMemoryStore",
]
