"""
Persistent query history store using ChromaDB.

Saves every successful NL → SQL pair and retrieves semantically similar
past queries to use as few-shot examples in the SQL Generator.

ChromaDB runs locally (./data/history_store/) so no external service needed.
"""

from __future__ import annotations

import hashlib
import os
from datetime import datetime
from typing import Any

try:
    import chromadb
    from chromadb.utils import embedding_functions

    CHROMADB_AVAILABLE = True
except ImportError:
    chromadb = None
    embedding_functions = None
    CHROMADB_AVAILABLE = False

_COLLECTION_NAME = "query_history"
_PERSIST_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "history_store")


def _get_collection() -> chromadb.Collection:
    if not CHROMADB_AVAILABLE:
        raise RuntimeError("ChromaDB is not installed.")

    client = chromadb.PersistentClient(path=_PERSIST_PATH)
    ef = embedding_functions.OpenAIEmbeddingFunction(
        api_key=os.environ.get("OPENAI_API_KEY", ""),
        model_name="text-embedding-3-small",
    )
    return client.get_or_create_collection(_COLLECTION_NAME, embedding_function=ef)


def save_query_to_history(question: str, sql: str, success: bool = True) -> None:
    """Persists a NL + SQL pair to the vector store."""
    if not success:
        return
    try:
        collection = _get_collection()
        doc_id = hashlib.md5(question.encode()).hexdigest()
        metadata = {
            "sql": sql,
            "timestamp": datetime.utcnow().isoformat(),
            "success": str(success),
        }
        collection.upsert(
            ids=[doc_id],
            documents=[question],
            metadatas=[metadata],
        )
    except Exception:
        return


def retrieve_similar_queries(question: str, top_k: int = 3) -> list[dict[str, Any]]:
    """Returns top_k most similar past (question, sql) pairs."""
    try:
        collection = _get_collection()
        results = collection.query(query_texts=[question], n_results=top_k)
    except Exception:
        return []

    items = []
    for doc, meta in zip(
        results.get("documents", [[]])[0],
        results.get("metadatas", [[]])[0],
    ):
        items.append({"question": doc, "sql": meta.get("sql", "")})
    return items


def get_history_count() -> int:
    """Returns total number of stored queries."""
    try:
        return _get_collection().count()
    except Exception:
        return 0


def clear_history() -> None:
    """Wipes the history store (useful for testing)."""
    if not CHROMADB_AVAILABLE:
        return
    client = chromadb.PersistentClient(path=_PERSIST_PATH)
    client.delete_collection(_COLLECTION_NAME)
