from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.startup import run_startup_validation


def test_startup_validation_reports_core_runtime_sections() -> None:
    diagnostics = run_startup_validation(strict=False)
    checks = {item["name"]: item for item in diagnostics["checks"]}

    assert diagnostics["status"] in {"ok", "degraded"}
    assert checks["environment"]["status"] in {"ok", "warning"}
    assert checks["connectors"]["status"] == "ok"
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
