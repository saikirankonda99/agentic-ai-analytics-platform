import os
from uuid import uuid4

import pytest

from backend.persistence import PersistenceError, WorkspaceDocument, build_auth_session_repository, build_workspace_repository


def test_postgres_restart_revocation_and_stale_save_protection():
    url = os.getenv("TEST_POSTGRES_URL")
    if os.getenv("RUN_SERVICE_TESTS") != "1" or not url:
        pytest.skip("A disposable PostgreSQL service is required.")
    key = f"service-test.{uuid4().hex}"
    repo = build_workspace_repository(url)
    auth = build_auth_session_repository(url)
    try:
        repo.save(WorkspaceDocument(key, "service-test", {"saved_reports": [{"title": "Retained report"}]}))
        auth.create_session(key, {"user_id": "test", "workspace_id": key,
                                  "created_at": "2026-01-01T00:00:00+00:00", "expires_at": "2027-01-01T00:00:00+00:00"})
        fresh = build_workspace_repository(url)
        stale = fresh.get(key)
        assert stale.memory["saved_reports"][0]["title"] == "Retained report"
        assert build_auth_session_repository(url).get_session(key)["workspace_id"] == key
        assert fresh.delete(key, "service-test") == 1
        with pytest.raises(PersistenceError):
            repo.save(stale)
        assert fresh.get(key) is None
        assert auth.delete_session(key)
        assert build_auth_session_repository(url).get_session(key) is None
    finally:
        repo.delete(key, "service-test")
        auth.delete_session(key)
