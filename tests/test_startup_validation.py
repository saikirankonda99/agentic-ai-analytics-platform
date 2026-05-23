from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.config import AppSettings, get_settings, validate_settings
from backend.startup import run_startup_validation


def test_startup_validation_reports_core_runtime_sections() -> None:
    diagnostics = run_startup_validation(strict=False)
    checks = {item["name"]: item for item in diagnostics["checks"]}

    assert diagnostics["status"] in {"ok", "degraded"}
    assert checks["environment"]["status"] in {"ok", "warning"}
    assert checks["connectors"]["status"] == "ok"
    assert checks["workflow_database"]["status"] == "ok"
    assert checks["telemetry"]["status"] == "ok"
    assert checks["orchestration"]["status"] == "ok"


def test_strict_startup_raises_for_required_connector_failure(monkeypatch) -> None:
    import backend.startup as startup

    monkeypatch.setattr(
        startup,
        "_connector_check",
        lambda validate_connectors: startup.StartupCheck("connectors", "error", "required connector unavailable"),
    )

    with pytest.raises(RuntimeError):
        run_startup_validation(strict=True)


def test_health_readiness_and_diagnostics_endpoints_include_runtime_validation() -> None:
    client = TestClient(app)

    health = client.get("/health").json()
    readiness = client.get("/readiness").json()
    diagnostics = client.get("/diagnostics").json()

    assert health["status"] == "ok"
    assert readiness["status"] in {"ready", "degraded"}
    assert diagnostics["startup"]["summary"]["error"] == 0
    assert "connectors" in diagnostics
    assert "auth" in diagnostics


def test_workflow_database_url_has_precedence_over_database_url(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://platform:secret@db.example.com:5432/platform")
    monkeypatch.setenv("WORKFLOW_DATABASE_URL", "sqlite:///data/workflow-specific.db")

    settings = get_settings()

    assert settings.database_backend == "postgresql"
    assert settings.workflow_database_backend == "sqlite"
    assert settings.workflow_database_url == "sqlite:///data/workflow-specific.db"
    assert settings.workflow_database_source == "WORKFLOW_DATABASE_URL"


def test_workflow_database_url_falls_back_to_database_url_for_compatibility(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://platform:secret@db.example.com:5432/platform")
    monkeypatch.delenv("WORKFLOW_DATABASE_URL", raising=False)

    settings = get_settings()
    diagnostics = validate_settings(settings)

    assert settings.workflow_database_url == settings.database_url
    assert settings.workflow_database_source == "DATABASE_URL"
    assert settings.workflow_database_backend == "postgresql"
    assert any("compatibility fallback" in item for item in diagnostics["warnings"])


def test_production_rejects_postgres_platform_with_sqlite_workflow_storage() -> None:
    settings = AppSettings(
        environment="production",
        database_url="postgresql://platform:secret@db.example.com:5432/platform",
        workflow_database_url="sqlite:///data/workflow_runtime.db",
        workflow_database_source="WORKFLOW_DATABASE_URL",
        redis_url="redis://redis:6379/0",
    )

    diagnostics = validate_settings(settings)

    assert diagnostics["valid"] is False
    assert any("must not run workflow persistence on SQLite" in item for item in diagnostics["errors"])
    assert diagnostics["database_url"] == "postgresql://***@db.example.com:5432/platform"
