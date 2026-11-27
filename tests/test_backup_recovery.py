from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend import backup


def _database(path):
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("CREATE TABLE sales (id INTEGER PRIMARY KEY, revenue INTEGER NOT NULL)")
    connection.executemany("INSERT INTO sales(revenue) VALUES(?)", [(125,), (275,)])
    connection.commit()
    return connection


def test_online_sqlite_backup_restores_committed_wal_data_to_new_file(tmp_path):
    live = tmp_path / "live.db"
    connection = _database(live)
    try:
        snapshot = tmp_path / "backups" / "sales.snapshot"
        result = backup.create_backup(f"sqlite:///{live}", snapshot)
        assert result["engine"] == "sqlite"
        assert backup.verify_backup(snapshot)["sha256"] == result["sha256"]
        connection.execute("INSERT INTO sales(revenue) VALUES(999)")
        connection.commit()
        restored = tmp_path / "restore" / "sales.db"
        assert backup.restore_backup(snapshot, target=restored)["restored"]
        with sqlite3.connect(restored) as db:
            assert db.execute("SELECT SUM(revenue), COUNT(*) FROM sales").fetchone() == (400, 2)
        assert connection.execute("SELECT COUNT(*) FROM sales").fetchone()[0] == 3
        if os.name == "posix":
            assert snapshot.stat().st_mode & 0o777 == 0o600
            assert Path(result["manifest"]).stat().st_mode & 0o777 == 0o600
            assert restored.stat().st_mode & 0o777 == 0o600
    finally:
        connection.close()


def test_backup_and_restore_refuse_existing_destinations(tmp_path):
    live = tmp_path / "live.db"
    _database(live).close()
    snapshot = tmp_path / "snapshot"
    backup.create_backup(f"sqlite:///{live}", snapshot)
    with pytest.raises(backup.BackupError, match="already exists"):
        backup.create_backup(f"sqlite:///{live}", snapshot)
    before = live.read_bytes()
    with pytest.raises(backup.BackupError, match="already exists"):
        backup.restore_backup(snapshot, target=live)
    assert live.read_bytes() == before


def test_checksum_corruption_refuses_restore_before_target_creation(tmp_path):
    live = tmp_path / "live.db"
    _database(live).close()
    snapshot = tmp_path / "snapshot"
    backup.create_backup(f"sqlite:///{live}", snapshot)
    with snapshot.open("ab") as file:
        file.write(b"corruption")
    target = tmp_path / "restored.db"
    with pytest.raises(backup.BackupError, match="checksum or size"):
        backup.restore_backup(snapshot, target=target)
    assert not target.exists()


def test_bad_database_never_becomes_successful_snapshot(tmp_path):
    source = tmp_path / "source.db"
    source.write_bytes(b"not a database")
    snapshot = tmp_path / "snapshot"
    with pytest.raises((backup.BackupError, sqlite3.DatabaseError)):
        backup.create_backup(f"sqlite:///{source}", snapshot)
    assert not snapshot.exists()
    assert not backup._manifest_path(snapshot).exists()


def test_symlink_restore_target_is_not_followed(tmp_path):
    source = tmp_path / "source.db"
    _database(source).close()
    snapshot = tmp_path / "snapshot"
    backup.create_backup(f"sqlite:///{source}", snapshot)
    target = tmp_path / "link.db"
    target.symlink_to(source)
    with pytest.raises(backup.BackupError, match="already exists"):
        backup.restore_backup(snapshot, target=target)
    with sqlite3.connect(source) as connection:
        assert connection.execute("SELECT COUNT(*) FROM sales").fetchone() == (2,)


def test_postgres_credentials_stay_in_environment_and_restore_selects_database(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(backup.shutil, "which", lambda name: f"/tools/{name}")
    monkeypatch.setattr(backup, "_require_empty_postgres", lambda url: None)

    def run(arguments, **kwargs):
        calls.append((arguments, kwargs))
        if arguments[0].endswith("pg_dump"):
            Path(arguments[arguments.index("--file") + 1]).write_bytes(b"PGDMP fake archive for contract test")
        return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")

    monkeypatch.setattr(backup.subprocess, "run", run)
    source = "postgresql://source_user:private-source-secret@localhost/source"
    destination = "postgresql://restore_user:private-target-secret@localhost/restored"
    snapshot = tmp_path / "postgres.snapshot"
    result = backup.create_backup(source, snapshot)
    assert backup.restore_backup(snapshot, database_url=destination)["restored"]
    assert len(calls) == 2
    assert calls[0][1]["env"]["PGPASSWORD"] == "private-source-secret"
    assert calls[1][1]["env"]["PGPASSWORD"] == "private-target-secret"
    assert calls[1][0][calls[1][0].index("--dbname") + 1] == "restored"
    assert "--single-transaction" in calls[1][0]
    assert "--clean" not in calls[1][0]
    for arguments, _ in calls:
        assert "private-" not in str(arguments)
        assert "postgresql://" not in str(arguments)
    assert "private-" not in json.dumps(result)
    assert "source_user" not in backup._manifest_path(snapshot).read_text()


def test_postgres_tool_failure_does_not_expose_stderr(tmp_path, monkeypatch):
    monkeypatch.setattr(backup.shutil, "which", lambda name: f"/tools/{name}")
    monkeypatch.setattr(backup.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(
        returncode=1, stdout=b"", stderr=b"password=private-secret",
    ))
    target = tmp_path / "snapshot"
    with pytest.raises(backup.BackupError) as error:
        backup.create_backup("postgresql://owner:private-secret@localhost/source", target)
    assert "private-secret" not in str(error.value)
    assert not target.exists()


def test_postgres_restore_refuses_nonempty_target_without_calling_tool(monkeypatch):
    class Connection:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def execute(self, sql): return self
        def fetchone(self): return (1,)
    import psycopg
    monkeypatch.setattr(psycopg, "connect", lambda *args, **kwargs: Connection())
    with pytest.raises(backup.BackupError, match="empty target"):
        backup._require_empty_postgres("postgresql://unused/target")
