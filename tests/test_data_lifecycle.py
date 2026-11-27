from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json

import pytest

from backend.data_lifecycle import delete_workspace_data, run_retention
from backend.memory import MemoryDocument, build_vector_memory_store
from backend.persistence import PersistenceError, build_workspace_repository
from backend.retention import apply_workspace_retention
from workspace import build_user_session, load_workspace_memory, save_workspace_memory


@pytest.fixture
def lifecycle_storage(monkeypatch, tmp_path):
    import workspace
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'platform.db'}")
    monkeypatch.setenv("WORKFLOW_DATABASE_URL", f"sqlite:///{tmp_path / 'workflow.db'}")
    monkeypatch.setenv("VECTOR_DATABASE_URL", "")
    monkeypatch.setattr(workspace, "WORKSPACE_DIR", tmp_path / "legacy")
    return tmp_path


def test_production_storage_failure_never_uses_legacy_files(monkeypatch, lifecycle_storage):
    import workspace
    identity = build_user_session("owner", "shop", "analyst")
    legacy = workspace._workspace_path(identity["workspace_id"])
    legacy.write_text('{"query_history": [{"question": "old private data"}]}')
    original = legacy.read_bytes()
    monkeypatch.setenv("APP_ENV", "production")

    def unavailable():
        raise OSError("Storage unavailable")

    monkeypatch.setattr(workspace, "build_workspace_repository", unavailable)
    with pytest.raises(PersistenceError):
        load_workspace_memory(identity)
    with pytest.raises(PersistenceError):
        save_workspace_memory(identity, {"query_history": []})
    assert legacy.read_bytes() == original


def test_delete_is_scoped_and_stale_sessions_cannot_recreate_data(lifecycle_storage):
    owner = build_user_session("owner", "shop", "analyst")
    neighbor = build_user_session("owner", "other-shop", "analyst")
    for identity in (owner, neighbor):
        memory = load_workspace_memory(identity)
        memory["query_history"] = [{"question": identity["team_id"]}]
        save_workspace_memory(identity, memory)
        build_vector_memory_store().upsert(MemoryDocument(
            "sql_query", "sales", organization_id=f"organization:{identity['team_id']}",
            workspace_id=identity["workspace_id"], connector_id="sales", metadata={"sql": "SELECT 1"},
        ))
    stale = load_workspace_memory(owner)
    deleted = delete_workspace_data(owner)
    assert deleted["workspace_documents"] == 1
    assert deleted["memory"] == 1
    assert load_workspace_memory(owner)["query_history"] == []
    assert load_workspace_memory(neighbor)["query_history"][0]["question"] == "other-shop"
    assert len(build_vector_memory_store().search(
        "sales", organization_id="organization:other-shop", workspace_id=neighbor["workspace_id"],
    )) == 1
    with pytest.raises(PersistenceError, match="another session"):
        save_workspace_memory(owner, stale)
    fresh = load_workspace_memory(owner)
    fresh["query_history"] = [{"question": "new analysis"}]
    save_workspace_memory(owner, fresh)
    assert load_workspace_memory(owner)["query_history"][0]["question"] == "new analysis"


def test_cross_workspace_and_shared_nonadmin_deletion_are_rejected(lifecycle_storage):
    identity = build_user_session("analyst", "shop", "analyst")
    for target in ("another-shop.owner", "shop.shared", "shop.someone-else"):
        with pytest.raises(PermissionError):
            delete_workspace_data({**identity, "workspace_id": target})
    with pytest.raises(PermissionError):
        delete_workspace_data({**identity, "authenticated": False})


def test_retention_sweeps_inactive_workspaces_and_nested_transcripts(lifecycle_storage):
    now = datetime.now(timezone.utc)
    old = (now - timedelta(days=120)).isoformat()
    recent = (now - timedelta(days=1)).isoformat()
    identity = build_user_session("owner", "shop", "analyst")
    repository = build_workspace_repository()
    from backend.persistence import WorkspaceDocument
    repository.save(WorkspaceDocument(identity["workspace_id"], identity["team_id"], {
        "query_history": [{"question": "old", "timestamp": old}, {"question": "recent", "timestamp": recent}],
        "saved_reports": [{"title": "old", "created_at": old}, {"title": "recent", "created_at": recent}],
        "sessions": [{"updated_at": recent, "transcripts": [
            {"question": "old", "timestamp": old}, {"question": "recent", "timestamp": recent},
        ]}],
    }))
    counts = run_retention(now=now)
    assert counts["workspace_documents"] == 1
    remaining = repository.get(identity["workspace_id"]).memory
    assert [x["question"] for x in remaining["query_history"]] == ["recent"]
    assert [x["title"] for x in remaining["saved_reports"]] == ["recent"]
    assert [x["question"] for x in remaining["sessions"][0]["transcripts"]] == ["recent"]


def test_undated_legacy_records_expire_after_one_migration_window():
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    original = {"query_history": [{"question": "legacy"}]}
    migrated = apply_workspace_retention(original, now=now, history_days=30)
    assert "_retained_at" not in json.dumps(original)
    expired = apply_workspace_retention(migrated, now=now + timedelta(days=31), history_days=30)
    assert expired["query_history"] == []


def test_retention_does_not_overwrite_a_concurrent_saved_report(monkeypatch, lifecycle_storage):
    import backend.data_lifecycle as lifecycle
    from backend.persistence import WorkspaceDocument
    now = datetime.now(timezone.utc)
    old = (now - timedelta(days=120)).isoformat()
    repo = build_workspace_repository()
    target = "shop.owner"
    repo.save(WorkspaceDocument(target, "shop", {"saved_reports": [{"title": "expired", "created_at": old}]}))
    real_prune = lifecycle.apply_workspace_retention

    def concurrently_saved(memory, **kwargs):
        repo.save(WorkspaceDocument(target, "shop", {"saved_reports": [{"title": "fresh work", "created_at": now.isoformat()}]}))
        return real_prune(memory, **kwargs)

    monkeypatch.setattr(lifecycle, "apply_workspace_retention", concurrently_saved)
    counts = run_retention(now=now)
    assert counts["workspace_documents"] == 0
    assert repo.get(target).memory["saved_reports"][0]["title"] == "fresh work"


def test_repository_blocks_cross_team_identifier_collision(lifecycle_storage):
    from backend.persistence import WorkspaceDocument
    repo = build_workspace_repository()
    repo.save(WorkspaceDocument("acme.north.sam", "acme.north", {"query_history": [{"question": "private"}]}))
    collision = build_user_session("north.sam", "acme", "analyst")
    with pytest.raises(PersistenceError, match="ownership"):
        load_workspace_memory(collision)
    with pytest.raises(PersistenceError, match="ownership"):
        repo.save(WorkspaceDocument("acme.north.sam", "acme", {"query_history": []}))


@pytest.mark.parametrize("url", ["mysql://example.invalid/app", "sqlite:///", "sqlite:///:memory:", "postgresql://localhost", ""])
def test_invalid_storage_configuration_never_selects_a_different_database(url):
    from backend.persistence import PersistenceSettings
    from backend.config import AppSettings
    with pytest.raises(ValueError):
        PersistenceSettings(database_url=url)
    with pytest.raises(ValueError):
        AppSettings(database_url=url)
