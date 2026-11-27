"""Operator backup/restore commands. Secrets are read from environment, never printed.

SQLite uses its online backup API. PostgreSQL uses pg_dump/pg_restore with
connection credentials passed through libpq environment variables.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class BackupError(RuntimeError):
    pass


def _engine(database_url: str) -> str:
    if database_url.startswith("sqlite:///"):
        return "sqlite"
    if database_url.startswith(("postgresql://", "postgres://")):
        return "postgresql"
    raise BackupError("Backup requires an explicit SQLite or PostgreSQL database URL.")


def _manifest_path(snapshot: Path) -> Path:
    return snapshot.with_name(snapshot.name + ".manifest.json")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _reserve_new_file(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(descriptor)
    except FileExistsError as exc:
        raise BackupError("Destination already exists; choose a new path.") from exc


def _check_sqlite(path: Path) -> None:
    try:
        with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as connection:
            result = connection.execute("PRAGMA integrity_check").fetchall()
        if result != [("ok",)]:
            raise BackupError("SQLite snapshot failed its integrity check.")
    except sqlite3.Error as exc:
        raise BackupError("SQLite snapshot is not a valid, intact database.") from exc


def _postgres_environment(database_url: str) -> dict[str, str]:
    try:
        from psycopg.conninfo import conninfo_to_dict
        parameters = conninfo_to_dict(database_url)
    except Exception as exc:
        raise BackupError("Invalid PostgreSQL connection configuration.") from exc
    mapping = {
        "host": "PGHOST", "hostaddr": "PGHOSTADDR", "port": "PGPORT", "dbname": "PGDATABASE",
        "user": "PGUSER", "password": "PGPASSWORD", "sslmode": "PGSSLMODE",
        "sslrootcert": "PGSSLROOTCERT", "sslcert": "PGSSLCERT", "sslkey": "PGSSLKEY",
        "sslcrl": "PGSSLCRL", "connect_timeout": "PGCONNECT_TIMEOUT", "application_name": "PGAPPNAME",
        "options": "PGOPTIONS", "target_session_attrs": "PGTARGETSESSIONATTRS", "passfile": "PGPASSFILE",
        "channel_binding": "PGCHANNELBINDING",
    }
    database_name = parameters.get("dbname", "")
    if not database_name or "=" in database_name or database_name.startswith(("postgresql://", "postgres://")) or set(parameters) - set(mapping):
        raise BackupError("PostgreSQL backup needs an explicit database and supported libpq connection options.")
    environment = {key: value for key, value in os.environ.items() if not key.startswith("PG")}
    environment.update({mapping[key]: str(value) for key, value in parameters.items()})
    environment.setdefault("PGCONNECT_TIMEOUT", "10")
    return environment


def _run_postgres_tool(name: str, arguments: list[str], environment: dict[str, str]) -> None:
    executable = shutil.which(name)
    if not executable:
        raise BackupError(f"{name} is required; install the PostgreSQL client tools for the server version.")
    try:
        result = subprocess.run(
            [executable, *arguments], env=environment, capture_output=True, check=False, timeout=900,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise BackupError(f"{name} could not complete.") from exc
    if result.returncode:
        # stderr can contain connection details: never relay it into logs/chat.
        raise BackupError(f"{name} failed with exit code {result.returncode}; no restore was accepted as successful.")


def create_backup(database_url: str, output: str | Path) -> dict[str, Any]:
    engine = _engine(database_url)
    path = Path(output).absolute()
    manifest_path = _manifest_path(path)
    if path.exists() or path.is_symlink() or manifest_path.exists() or manifest_path.is_symlink():
        raise BackupError("Backup destination already exists; choose a new path.")
    if engine == "sqlite":
        source = Path(database_url.removeprefix("sqlite:///"))
        if not source.is_file():
            raise BackupError("The source SQLite database does not exist.")
    else:
        environment = _postgres_environment(database_url)
        if not shutil.which("pg_dump"):
            raise BackupError("pg_dump is required; install the PostgreSQL client tools for the server version.")
    _reserve_new_file(path)
    manifest_created = False
    try:
        if engine == "sqlite":
            with closing(sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True)) as connection:
                with closing(sqlite3.connect(path)) as target:
                    connection.backup(target)
            _check_sqlite(path)
        else:
            _run_postgres_tool("pg_dump", ["--format=custom", "--no-owner", "--no-privileges", "--file", str(path)], environment)
        with path.open("rb") as snapshot:
            os.fsync(snapshot.fileno())
        manifest = {
            "version": 1, "engine": engine, "format": "sqlite" if engine == "sqlite" else "pg_dump_custom",
            "created_at": datetime.now(timezone.utc).isoformat(), "sha256": _sha256(path),
            "bytes": path.stat().st_size,
        }
        _reserve_new_file(manifest_path)
        manifest_created = True
        with manifest_path.open("w", encoding="utf-8") as target:
            json.dump(manifest, target, sort_keys=True, indent=2)
            target.write("\n")
            target.flush()
            os.fsync(target.fileno())
        return {**manifest, "snapshot": str(path), "manifest": str(manifest_path)}
    except Exception:
        path.unlink(missing_ok=True)
        if manifest_created:
            manifest_path.unlink(missing_ok=True)
        raise


def verify_backup(snapshot: str | Path) -> dict[str, Any]:
    path = Path(snapshot).absolute()
    manifest_path = _manifest_path(path)
    try:
        if path.is_symlink() or manifest_path.is_symlink() or not path.is_file() or not manifest_path.is_file():
            raise BackupError("Snapshot and manifest must be regular files.")
        if manifest_path.stat().st_size > 16_384:
            raise BackupError("Invalid backup manifest.")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not isinstance(manifest, dict) or manifest.get("version") != 1:
            raise BackupError("Unsupported backup manifest.")
        if manifest.get("engine") not in {"sqlite", "postgresql"}:
            raise BackupError("Unsupported backup engine.")
        expected_format = "sqlite" if manifest["engine"] == "sqlite" else "pg_dump_custom"
        if manifest.get("format") != expected_format:
            raise BackupError("Backup format does not match its engine.")
        if manifest.get("bytes") != path.stat().st_size or manifest.get("sha256") != _sha256(path):
            raise BackupError("Backup checksum or size does not match; restore refused.")
        if manifest["engine"] == "sqlite":
            _check_sqlite(path)
        return manifest
    except (OSError, UnicodeError, ValueError) as exc:
        raise BackupError("Snapshot or manifest could not be verified.") from exc


def _require_empty_postgres(database_url: str) -> None:
    import psycopg
    try:
        with psycopg.connect(database_url, connect_timeout=10) as connection:
            row = connection.execute("""
                SELECT COUNT(*) FROM pg_class AS c
                JOIN pg_namespace AS n ON n.oid = c.relnamespace
                WHERE n.nspname NOT IN ('pg_catalog', 'information_schema')
                  AND n.nspname NOT LIKE 'pg_toast%'
                  AND c.relkind IN ('r', 'p', 'v', 'm', 'S', 'f')
            """).fetchone()
        if row[0]:
            raise BackupError("PostgreSQL restore requires an empty target database.")
    except BackupError:
        raise
    except Exception as exc:
        raise BackupError("The PostgreSQL restore target could not be checked.") from exc


def restore_backup(
    snapshot: str | Path, *, target: str | Path | None = None, database_url: str | None = None,
) -> dict[str, Any]:
    path = Path(snapshot).absolute()
    manifest = verify_backup(path)
    if manifest["engine"] == "sqlite":
        if target is None or database_url is not None:
            raise BackupError("SQLite restore requires a new target file path.")
        destination = Path(target).absolute()
        _reserve_new_file(destination)
        try:
            with path.open("rb") as source, destination.open("wb") as output:
                shutil.copyfileobj(source, output)
                output.flush()
                os.fsync(output.fileno())
            if _sha256(destination) != manifest["sha256"]:
                raise BackupError("Restored checksum does not match; restore refused.")
            _check_sqlite(destination)
        except Exception:
            destination.unlink(missing_ok=True)
            raise
        return {"engine": "sqlite", "restored": True, "target": str(destination)}
    if target is not None or not database_url or _engine(database_url) != "postgresql":
        raise BackupError("PostgreSQL restore requires a dedicated empty PostgreSQL target.")
    environment = _postgres_environment(database_url)
    _require_empty_postgres(database_url)
    _run_postgres_tool("pg_restore", [
        "--exit-on-error", "--single-transaction", "--no-owner", "--no-privileges",
        "--dbname", environment["PGDATABASE"], str(path),
    ], environment)
    return {"engine": "postgresql", "restored": True}


def _database_url(variable: str) -> str:
    value = os.getenv(variable)
    if not value:
        raise BackupError("The selected database environment variable is not configured.")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description="Create, verify and restore private database backups.")
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create")
    create.add_argument("--database-env", default="DATABASE_URL")
    create.add_argument("--output", required=True)
    verify = commands.add_parser("verify")
    verify.add_argument("--input", required=True)
    restore = commands.add_parser("restore")
    restore.add_argument("--input", required=True)
    destination = restore.add_mutually_exclusive_group(required=True)
    destination.add_argument("--target")
    destination.add_argument("--database-env")
    arguments = parser.parse_args()
    try:
        if arguments.command == "create":
            result = create_backup(_database_url(arguments.database_env), arguments.output)
        elif arguments.command == "verify":
            result = {**verify_backup(arguments.input), "verified": True}
        else:
            result = restore_backup(arguments.input, target=arguments.target,
                                    database_url=_database_url(arguments.database_env) if arguments.database_env else None)
        print(json.dumps(result, sort_keys=True))
        return 0
    except (BackupError, OSError, sqlite3.Error) as exc:
        # Expected messages are authored above; never print database exceptions.
        message = str(exc) if isinstance(exc, BackupError) else "Backup operation failed due to storage access."
        print(json.dumps({"error": message}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
