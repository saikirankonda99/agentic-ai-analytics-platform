import sqlite3

from graph import cost_tracker


def test_development_usage_never_persists_or_returns_customer_question(tmp_path, monkeypatch):
    path = tmp_path / "usage.db"
    monkeypatch.setattr(cost_tracker, "_DB_PATH", str(path))
    monkeypatch.setenv("APP_ENV", "development")
    cost_tracker.log_query_cost("Customer confidential payroll", "test-model", 0.02, 10)
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT question FROM query_log").fetchone() == (None,)
        connection.execute("UPDATE query_log SET question='Legacy customer secret'")
    assert cost_tracker.get_recent_queries()[0]["question"] is None
    assert cost_tracker.get_total_cost() == 0.02


def test_production_never_opens_global_usage_database(tmp_path, monkeypatch):
    path = tmp_path / "must-not-exist.db"
    monkeypatch.setattr(cost_tracker, "_DB_PATH", str(path))
    monkeypatch.setenv("APP_ENV", "production")
    cost_tracker.log_query_cost("Confidential", "test-model", 1, 5)
    assert cost_tracker.get_total_cost() is None
    assert cost_tracker.get_recent_queries() == []
    assert not path.exists()
