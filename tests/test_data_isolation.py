from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta, timezone

import pytest

from backend.connectors import ConnectorRegistry, PostgresConnectorConfig, SQLiteConnector, SQLiteConnectorConfig
from backend.memory import (
    HashingEmbeddingService, InMemoryVectorMemoryStore, MemoryDocument,
    RelationalVectorMemoryStore,
)
from graph import history_store


def _sales_database(path, amount):
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE sales (revenue INTEGER)")
        connection.execute("INSERT INTO sales VALUES (?)", (amount,))
    return str(path)


def _private_connector(path, organization="organization:store-a", workspaces=("store-a.owner",)):
    return SQLiteConnector(SQLiteConnectorConfig(
        connector_id="sales", database_path=str(path), organization_id=organization,
        workspace_ids=workspaces,
    ))


def test_connector_grants_require_both_organization_and_workspace(tmp_path):
    connector = _private_connector(_sales_database(tmp_path / "sales.db", 100))
    registry = ConnectorRegistry({"sales": connector})
    assert registry.get_for_workspace(
        "sales", organization_id="organization:store-a", workspace_id="store-a.owner",
    ).execute_read("SELECT revenue FROM sales")[1] == [(100,)]
    for organization, workspace in [
        ("organization:store-b", "store-a.owner"), ("organization:store-a", "store-b.owner"),
        ("organization:store-b", "store-b.owner"), ("", "store-a.owner"),
    ]:
        with pytest.raises(PermissionError):
            registry.get_for_workspace("sales", organization_id=organization, workspace_id=workspace)


def test_scoped_diagnostics_do_not_list_or_probe_another_organization(tmp_path, monkeypatch):
    private = _private_connector(_sales_database(tmp_path / "private.db", 123))
    monkeypatch.setattr(private, "health_check", lambda: pytest.fail("Unauthorized connector was probed"))
    registry = ConnectorRegistry({"sales": private, "sqlite": SQLiteConnector(SQLiteConnectorConfig())})
    report = registry.diagnostics_for_workspace(organization_id="organization:store-b", workspace_id="store-b.owner")
    assert [item["connector_id"] for item in report["connectors"]] == ["sqlite"]
    assert set(report["health"]) == {"sqlite"}
    assert str(tmp_path / "private.db") not in json.dumps(report)


def test_unscoped_access_cannot_turn_private_database_into_example(tmp_path, monkeypatch):
    import db

    connector = SQLiteConnector(SQLiteConnectorConfig(
        database_path=_sales_database(tmp_path / "private.db", 900), public_demo=True,
    ))
    registry = ConnectorRegistry({"sqlite": connector})
    monkeypatch.setattr(db, "get_connector_registry", lambda: registry)
    with pytest.raises(PermissionError, match="bundled example"):
        db.run_query("SELECT revenue FROM sales")
    with pytest.raises(PermissionError, match="Both organization"):
        db.get_schema(organization_id="organization:a")


def test_current_grants_are_checked_even_for_identical_previously_successful_sql(tmp_path, monkeypatch):
    import db

    path = _sales_database(tmp_path / "sales.db", 250)
    registry = ConnectorRegistry({"sales": _private_connector(path)})
    monkeypatch.setattr(db, "get_connector_registry", lambda: registry)
    scope = {"organization_id": "organization:store-a", "workspace_id": "store-a.owner", "connector_id": "sales"}
    assert db.run_query("SELECT revenue FROM sales", **scope)[1] == [(250,)]
    registry._connectors["sales"] = _private_connector(path, workspaces=("store-a.other",))
    with pytest.raises(PermissionError, match="not authorized"):
        db.run_query("SELECT revenue FROM sales", **scope)
    with pytest.raises(PermissionError, match="not authorized"):
        db.get_schema(**scope)


def test_bundled_example_is_explicitly_available_without_private_grants():
    registry = ConnectorRegistry({"sqlite": SQLiteConnector(SQLiteConnectorConfig())})
    result = registry.get_for_workspace(
        "sqlite", organization_id="organization:example", workspace_id="example.customer",
    ).execute_read("SELECT COUNT(*) FROM Invoice")
    assert result[1] == [(412,)]


def test_server_connector_configuration_is_not_implicitly_shared(tmp_path, monkeypatch):
    from backend.connectors import default_connectors

    path = _sales_database(tmp_path / "store.db", 333)
    monkeypatch.setenv("ANALYTICS_CONNECTORS_JSON", json.dumps([{
        "connector_id": "store-a-sales", "kind": "sqlite", "database_path": path,
        "organization_id": "organization:store-a", "workspace_ids": ["store-a.owner"],
    }]))
    registry = ConnectorRegistry(default_connectors())
    assert registry.get_for_workspace(
        "store-a-sales", organization_id="organization:store-a", workspace_id="store-a.owner",
    ).execute_read("SELECT revenue FROM sales")[1] == [(333,)]
    with pytest.raises(PermissionError):
        registry.get_for_workspace("store-a-sales", organization_id="organization:store-b", workspace_id="store-b.owner")
    monkeypatch.setenv("ANALYTICS_CONNECTORS_JSON", json.dumps([{"connector_id": "unowned", "kind": "sqlite"}]))
    with pytest.raises(ValueError, match="Invalid server"):
        default_connectors()


@pytest.mark.parametrize("dsn", [
    "host=localhost dbname=store user=owner password=private-secret",
    "postgresql://owner:private-secret@localhost/store?password=second-secret",
])
def test_connector_diagnostics_do_not_expose_credentials(dsn):
    public = PostgresConnectorConfig(dsn=dsn).public_dict()
    assert "private-secret" not in str(public)
    assert "second-secret" not in str(public)


@pytest.mark.parametrize("persistent", [False, True])
def test_memory_isolated_by_org_workspace_and_connector(tmp_path, persistent):
    url = f"sqlite:///{tmp_path / 'memory.db'}"
    store = RelationalVectorMemoryStore(url) if persistent else InMemoryVectorMemoryStore()
    for organization, workspace, connector, sql in [
        ("org-a", "main", "sales", "SELECT 10"),
        ("org-b", "main", "sales", "SELECT 20"),
        ("org-a", "other", "sales", "SELECT 30"),
        ("org-a", "main", "payroll", "SELECT 40"),
    ]:
        store.upsert(MemoryDocument(
            namespace="sql_query", text="total revenue", organization_id=organization,
            workspace_id=workspace, connector_id=connector, metadata={"sql": sql},
        ))
    if persistent:
        store = RelationalVectorMemoryStore(url)  # A fresh process-equivalent instance.
    found = store.search("total revenue", organization_id="org-a", workspace_id="main",
                         namespace="sql_query", connector_id="sales")
    assert [item.metadata["sql"] for item in found] == ["SELECT 10"]
    assert store.delete_workspace(organization_id="org-a", workspace_id="main") == 2
    assert store.search("revenue", organization_id="org-a", workspace_id="main") == ()
    assert len(store.search("revenue", organization_id="org-b", workspace_id="main")) == 1
    assert len(store.search("revenue", organization_id="org-a", workspace_id="other")) == 1


def test_upsert_updates_example_in_same_scope_without_overwriting_other_customer(tmp_path):
    store = RelationalVectorMemoryStore(f"sqlite:///{tmp_path / 'memory.db'}")
    for org, sql in [("a", "SELECT 1"), ("b", "SELECT 2"), ("a", "SELECT 3")]:
        store.upsert(MemoryDocument(namespace="sql_query", text="sales", organization_id=org,
                                    workspace_id="main", connector_id="sales", metadata={"sql": sql}))
    assert store.count(organization_id="a", workspace_id="main") == 1
    assert store.search("sales", organization_id="a", workspace_id="main")[0].metadata["sql"] == "SELECT 3"
    assert store.search("sales", organization_id="b", workspace_id="main")[0].metadata["sql"] == "SELECT 2"


def test_history_rejects_missing_scope_and_scoped_delete_preserves_other_business(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'history.db'}")
    monkeypatch.delenv("VECTOR_DATABASE_URL", raising=False)
    scope_a = {"organization_id": "organization:a", "workspace_id": "same", "connector_id": "sales"}
    scope_b = {**scope_a, "organization_id": "organization:b"}
    assert history_store.save_query_to_history("sales", "SELECT 100", **scope_a)
    assert history_store.save_query_to_history("sales", "SELECT 900", **scope_b)
    assert not history_store.save_query_to_history("unscoped", "SELECT 0")
    assert history_store.retrieve_similar_queries("sales") == []
    assert history_store.get_history_count() == 0
    assert history_store.retrieve_similar_queries("sales", **scope_a) == [{"question": "sales", "sql": "SELECT 100"}]
    assert history_store.delete_scope(organization_id="organization:a", workspace_id="same") == 1
    assert history_store.retrieve_similar_queries("sales", **scope_a) == []
    assert history_store.retrieve_similar_queries("sales", **scope_b) == [{"question": "sales", "sql": "SELECT 900"}]


def test_embeddings_are_reproducible_across_python_hash_seeds():
    code = "from backend.memory import HashingEmbeddingService; print(HashingEmbeddingService().embed('Store sales revenue'))"
    results = [subprocess.check_output([sys.executable, "-c", code], text=True,
                                      env={**os.environ, "PYTHONHASHSEED": str(seed)}) for seed in [1, 999]]
    assert results[0] == results[1]
    assert sum(x * x for x in HashingEmbeddingService().embed("")) == 1


def test_retention_removes_only_old_records_and_requires_explicit_timezone(tmp_path):
    path = tmp_path / "retention.db"
    store = RelationalVectorMemoryStore(f"sqlite:///{path}")
    old = store.upsert(MemoryDocument(namespace="workflow_context", text="old", organization_id="a", workspace_id="w"))
    store.upsert(MemoryDocument(namespace="workflow_context", text="current", organization_id="a", workspace_id="w"))
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE analytics_memory SET updated_at=? WHERE memory_id=?",
                           ((datetime.now(timezone.utc) - timedelta(days=60)).isoformat(), old.memory_id))
    with pytest.raises(ValueError, match="timezone"):
        store.prune_before("2026-01-01")
    assert store.prune_before((datetime.now(timezone.utc) - timedelta(days=30)).isoformat()) == 1
    assert [item.text for item in store.search("current", organization_id="a", workspace_id="w")] == ["current"]


@pytest.mark.parametrize("database_url", ["sqlite:///", "sqlite:///   "])
def test_memory_store_rejects_empty_sqlite_path(database_url):
    with pytest.raises(ValueError, match="requires a file path"):
        RelationalVectorMemoryStore(database_url)
