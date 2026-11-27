"""Live PostgreSQL/pgvector persistence gates (service-backed CI)."""
import os
from uuid import uuid4

import pytest

from backend.memory import MemoryDocument, PgVectorMemoryStore, RelationalVectorMemoryStore


@pytest.mark.parametrize("use_pgvector", [False, True])
def test_postgres_memory_roundtrip_with_real_service(use_pgvector):
    url = os.getenv("TEST_POSTGRES_URL")
    if os.getenv("RUN_SERVICE_TESTS") != "1" or not url:
        pytest.skip("RUN_SERVICE_TESTS=1 and TEST_POSTGRES_URL are required")
    cls = PgVectorMemoryStore if use_pgvector else RelationalVectorMemoryStore
    organization = f"test:{uuid4()}"
    neighbor = f"test:{uuid4()}"
    try:
        store = cls(url)
        for org, sql in [(organization, "SELECT 11"), (neighbor, "SELECT 22")]:
            store.upsert(MemoryDocument(namespace="sql_query", text="total sales", organization_id=org,
                                        workspace_id="main", connector_id="sales", metadata={"sql": sql}))
        fresh = cls(url)
        assert [row.metadata["sql"] for row in fresh.search(
            "sales", organization_id=organization, workspace_id="main", connector_id="sales",
        )] == ["SELECT 11"]
        assert fresh.delete_workspace(organization_id=organization, workspace_id="main") == 1
        assert len(fresh.search("sales", organization_id=neighbor, workspace_id="main")) == 1
    finally:
        cls(url).delete_workspace(organization_id=organization, workspace_id="main")
        cls(url).delete_workspace(organization_id=neighbor, workspace_id="main")
