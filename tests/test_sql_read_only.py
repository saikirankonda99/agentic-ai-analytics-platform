from __future__ import annotations

import sqlite3
from types import SimpleNamespace

import pytest

from backend.connectors import PostgresConnector, PostgresConnectorConfig, SQLiteConnector, SQLiteConnectorConfig
from guardrails import is_safe_sql


@pytest.fixture
def sales_connector(tmp_path):
    database = tmp_path / "sales.db"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE sales (amount INTEGER)")
        connection.executemany("INSERT INTO sales VALUES (?)", [(10,), (20,), (30,)])
    return SQLiteConnector(SQLiteConnectorConfig(database_path=str(database)))


@pytest.mark.parametrize("sql", [
    "PRAGMA user_version=7", "VACUUM", "DELETE FROM sales", "UPDATE sales SET amount=0",
    "SELECT 1; SELECT 2", "WITH x AS (DELETE FROM sales RETURNING *) SELECT * FROM x",
    "SELECT 1 INTO copied", "SELECT load_extension('anything')", "SELECT 1 /* unfinished",
    'SELECT "load_extension"(\'anything\')', 'SELECT "pg_catalog"."lo_export"(1, \'anything\')',
])
def test_non_read_queries_are_rejected_without_changing_data(sales_connector, sql):
    assert not is_safe_sql(sql)
    with pytest.raises(ValueError, match="read-only"):
        sales_connector.execute_read(sql)
    assert sales_connector.execute_read("SELECT SUM(amount) FROM sales")[1] == [(60,)]


def test_read_queries_allow_comments_literals_and_ctes(sales_connector):
    assert sales_connector.execute_read("/* safe comment */ SELECT SUM(amount) FROM sales;")[1] == [(60,)]
    assert sales_connector.execute_read("WITH totals AS (SELECT SUM(amount) AS total FROM sales) SELECT total FROM totals")[1] == [(60,)]
    assert sales_connector.execute_read("SELECT 'delete; -- literal' AS label FROM sales LIMIT 1")[1] == [("delete; -- literal",)]


def test_sqlite_database_permissions_still_block_writes_if_filter_is_bypassed(sales_connector, monkeypatch):
    import backend.connectors as connectors

    monkeypatch.setattr(connectors, "is_safe_sql", lambda sql: True)
    with pytest.raises(sqlite3.DatabaseError):
        sales_connector.execute_read("DELETE FROM sales")
    with pytest.raises(sqlite3.DatabaseError):
        sales_connector.execute_read("PRAGMA user_version=7")
    with sqlite3.connect(sales_connector.database_path) as connection:
        assert connection.execute("SELECT SUM(amount) FROM sales").fetchone() == (60,)
        assert connection.execute("PRAGMA user_version").fetchone() == (0,)


def test_sqlite_missing_database_is_not_created(tmp_path):
    database = tmp_path / "missing.db"
    connector = SQLiteConnector(SQLiteConnectorConfig(database_path=str(database)))
    assert connector.health_check().status == "unavailable"
    assert not database.exists()


def test_query_row_limit_is_enforced(sales_connector, monkeypatch):
    monkeypatch.setenv("SQL_MAX_ROWS", "2")
    with pytest.raises(ValueError, match="row limit"):
        sales_connector.execute_read("SELECT amount FROM sales")
    assert len(sales_connector.execute_read("SELECT amount FROM sales LIMIT 2")[1]) == 2


def test_postgres_requests_read_only_transaction_and_timeout(monkeypatch):
    calls = []

    class Cursor:
        description = [SimpleNamespace(name="total")]
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def execute(self, sql, params=None):
            assert connection.read_only is True
            calls.append((sql, params))
        def fetchmany(self, size):
            return [(60,)]

    class Connection:
        read_only = False
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def cursor(self):
            return Cursor()

    connection = Connection()
    connector = PostgresConnector(PostgresConnectorConfig(dsn="unused"))
    monkeypatch.setattr(connector, "_connect", lambda: connection)
    assert connector.execute_read("SELECT SUM(amount) AS total FROM sales") == (["total"], [(60,)])
    assert "statement_timeout" in calls[0][0]
    assert calls[1][0].startswith("SELECT SUM")
