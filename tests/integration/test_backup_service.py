"""Real PostgreSQL recovery and customer-role checks on disposable databases only."""
from __future__ import annotations

import os
import secrets
import shutil
from decimal import Decimal
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit
from uuid import uuid4

import pytest

from backend.backup import BackupError, create_backup, restore_backup
from backend.connectors import ConnectorRegistry, PostgresConnector, PostgresConnectorConfig
from backend.persistence import PersistenceError, PostgreSQLWorkspaceRepository, WorkspaceDocument


def _database_url(base: str, database: str, *, user: str | None = None, password: str | None = None) -> str:
    """Change only generated database/role targets, and verify libpq agrees."""
    from psycopg.conninfo import conninfo_to_dict

    parts = urlsplit(base)
    if parts.scheme not in {"postgres", "postgresql"}:
        pytest.fail("Service tests require a PostgreSQL URI.")
    netloc = parts.netloc
    removed = {"dbname"}
    if user is not None:
        netloc = quote(user, safe="") + ":" + quote(password or "", safe="") + "@" + netloc.rsplit("@", 1)[-1]
        removed.update({"user", "password"})
    query = urlencode([(key, value) for key, value in parse_qsl(parts.query) if key not in removed])
    result = urlunsplit((parts.scheme, netloc, "/" + quote(database, safe=""), query, ""))
    parsed = conninfo_to_dict(result)
    if parsed.get("dbname") != database or (user is not None and parsed.get("user") != user):
        pytest.fail("Could not select the disposable database/role safely.")
    return result


@pytest.fixture
def postgres_tools():
    if not shutil.which("pg_dump") or not shutil.which("pg_restore"):
        pytest.skip("Matching PostgreSQL pg_dump and pg_restore client tools are required")


@pytest.fixture
def disposable_databases():
    if os.getenv("RUN_SERVICE_TESTS") != "1" or not os.getenv("TEST_POSTGRES_URL"):
        pytest.skip("RUN_SERVICE_TESTS=1 and TEST_POSTGRES_URL are required")
    import psycopg
    from psycopg import sql

    base = os.environ["TEST_POSTGRES_URL"]
    prefix = "analytics_drill_" + uuid4().hex[:20]
    names = [prefix + "_source", prefix + "_restore"]
    created = []
    roles = []
    try:
        with psycopg.connect(base, autocommit=True, connect_timeout=10) as admin:
            for name in names:
                admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
                created.append(name)
        yield {
            "source": _database_url(base, names[0]), "restore": _database_url(base, names[1]),
            "source_name": names[0], "prefix": prefix, "roles": roles, "admin_url": base,
        }
    finally:
        # Only this fixture's successfully created, UUID-named databases/roles
        # can enter this list. The shared TEST_POSTGRES_URL database is untouched.
        if created or roles:
            with psycopg.connect(base, autocommit=True, connect_timeout=10) as admin:
                for name in reversed(created):
                    if not name.startswith(prefix + "_"):
                        raise RuntimeError("Refusing to clean a database outside this test's namespace.")
                    admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))
                for role in roles:
                    if not role.startswith(prefix + "_"):
                        raise RuntimeError("Refusing to clean a role outside this test's namespace.")
                    admin.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(role)))


def _seed_sales(database_url):
    import psycopg
    with psycopg.connect(database_url) as connection:
        connection.execute("CREATE TABLE sales (id INTEGER PRIMARY KEY, product TEXT NOT NULL, revenue NUMERIC(10,2))")
        for row in [(1, "mug", "30.00"), (2, "coffee", "60.25"), (3, "refund", "-5.25")]:
            connection.execute("INSERT INTO sales VALUES (%s, %s, %s)", row)


def test_postgresql_backup_restore_drill_preserves_rows_and_workspace_generation(
    postgres_tools, disposable_databases, tmp_path,
):
    import psycopg
    source = disposable_databases["source"]
    target = disposable_databases["restore"]
    _seed_sales(source)
    original = PostgreSQLWorkspaceRepository(source)
    original.save(WorkspaceDocument("drill.owner", "drill", {"_data_generation": 0, "report": "old"}))
    assert original.delete("drill.owner", "drill") == 1
    original.save(WorkspaceDocument("drill.owner", "drill", {"_data_generation": 1, "report": "retained"}))
    snapshot = tmp_path / "postgres.snapshot"
    create_backup(source, snapshot)
    with psycopg.connect(source) as connection:
        connection.execute("INSERT INTO sales VALUES (4, 'after backup', 999.00)")
    assert restore_backup(snapshot, database_url=target)["restored"]
    with psycopg.connect(target) as connection:
        assert connection.execute("SELECT COUNT(*), SUM(revenue) FROM sales").fetchone() == (3, Decimal("85.00"))
        assert connection.execute("SELECT product FROM sales ORDER BY id").fetchall() == [("mug",), ("coffee",), ("refund",)]
    restored = PostgreSQLWorkspaceRepository(target)
    assert restored.generation("drill.owner") == 1
    assert restored.get("drill.owner").memory == {"_data_generation": 1, "report": "retained"}
    with pytest.raises(PersistenceError, match="deleted in another session"):
        restored.save(WorkspaceDocument("drill.owner", "drill", {"_data_generation": 0, "report": "stale"}))
    with pytest.raises(BackupError, match="empty target"):
        restore_backup(snapshot, database_url=target)
    with psycopg.connect(source) as connection:
        assert connection.execute("SELECT COUNT(*) FROM sales").fetchone() == (4,)


def test_corrupted_postgresql_snapshot_is_refused_before_target_changes(postgres_tools, disposable_databases, tmp_path):
    import psycopg
    _seed_sales(disposable_databases["source"])
    snapshot = tmp_path / "postgres.snapshot"
    create_backup(disposable_databases["source"], snapshot)
    with snapshot.open("ab") as stream:
        stream.write(b"corrupt")
    with pytest.raises(BackupError, match="checksum or size"):
        restore_backup(snapshot, database_url=disposable_databases["restore"])
    with psycopg.connect(disposable_databases["restore"]) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public'"
        ).fetchone() == (0,)


def test_private_postgresql_connector_grants_and_read_only_role(disposable_databases, monkeypatch):
    import psycopg
    from psycopg import sql
    import backend.connectors as connectors

    role = disposable_databases["prefix"] + "_reader"
    password = secrets.token_urlsafe(24)
    source = disposable_databases["source"]
    with psycopg.connect(disposable_databases["admin_url"], autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(sql.Identifier(role), sql.Literal(password)))
        disposable_databases["roles"].append(role)
    with psycopg.connect(source) as connection:
        connection.execute("CREATE SCHEMA customer_a")
        connection.execute("CREATE SCHEMA customer_b")
        connection.execute("CREATE TABLE customer_a.sales (revenue INTEGER)")
        connection.execute("CREATE TABLE customer_b.sales (revenue INTEGER)")
        connection.execute("INSERT INTO customer_a.sales VALUES (352)")
        connection.execute("INSERT INTO customer_b.sales VALUES (999)")
        connection.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
            sql.Identifier(disposable_databases["source_name"]), sql.Identifier(role),
        ))
        connection.execute(sql.SQL("GRANT USAGE ON SCHEMA customer_a TO {}").format(sql.Identifier(role)))
        connection.execute(sql.SQL("GRANT SELECT ON customer_a.sales TO {}").format(sql.Identifier(role)))
    readonly_url = _database_url(source, disposable_databases["source_name"], user=role, password=password)
    connector = PostgresConnector(PostgresConnectorConfig(
        connector_id="customer-a", dsn=readonly_url, schema="customer_a",
        organization_id="organization:a", workspace_ids=("a.owner",),
    ))
    registry = ConnectorRegistry({"customer-a": connector})
    selected = registry.get_for_workspace("customer-a", organization_id="organization:a", workspace_id="a.owner")
    assert selected.execute_read("SELECT SUM(revenue) FROM customer_a.sales")[1] == [(352,)]
    assert selected.inspect_schema()["table_count"] == 1
    with pytest.raises(PermissionError):
        registry.get_for_workspace("customer-a", organization_id="organization:b", workspace_id="a.owner")
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        selected.execute_read("SELECT revenue FROM customer_b.sales")
    # Even if application validation regresses, database privileges/read-only
    # transaction settings remain the final write boundary.
    monkeypatch.setattr(connectors, "is_safe_sql", lambda statement: True)
    with pytest.raises((psycopg.errors.ReadOnlySqlTransaction, psycopg.errors.InsufficientPrivilege)):
        selected.execute_read("UPDATE customer_a.sales SET revenue=0")
    with psycopg.connect(source) as connection:
        assert connection.execute("SELECT SUM(revenue) FROM customer_a.sales").fetchone() == (352,)
