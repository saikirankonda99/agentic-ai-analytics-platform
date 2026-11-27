from __future__ import annotations

import json
import os
import secrets
import hashlib
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

from backend.persistence import PersistenceError, build_auth_session_repository
from workspace import build_user_session, team_workspace_id


SESSION_TTL_HOURS = max(1, int(os.getenv("AUTH_SESSION_TTL_HOURS", "12")))
# Kept for diagnostics compatibility; session authentication never reads this legacy file.
AUTH_SESSION_PATH = Path(os.getenv("AUTH_SESSION_PATH", "data/auth_sessions.json"))


@dataclass(frozen=True)
class AuthUser:
    username: str
    password_hash: str = field(repr=False)
    display_name: str
    team_id: str = "default-team"
    role: str = "analyst"
    credential_fingerprint: str = field(default="", repr=False)


@dataclass(frozen=True)
class AuthSession:
    session_token: str
    user_id: str
    display_name: str
    team_id: str
    workspace_id: str
    role: str
    created_at: str
    expires_at: str
    auth_fingerprint: str = field(default="", repr=False)

    def as_identity(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "display_name": self.display_name,
            "team_id": self.team_id,
            "workspace_id": self.workspace_id,
            "role": self.role,
            "auth_provider": "session-local",
            "authenticated": True,
            "session_token": self.session_token,
            "expires_at": self.expires_at,
        }


def _canonical_identifier(value: Any) -> bool:
    """Reject identifiers that workspace helpers would sanitize or merge."""
    return (
        isinstance(value, str)
        and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", value) is not None
        and not value.endswith("-")
    )


def _credential_fingerprint(kind: str, value: str) -> str:
    encoded = json.dumps(["analytics-credential-v1", kind, value], separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


@lru_cache(maxsize=16)
def _configured_user_snapshot(raw: str, production: bool, development_passwords: tuple[str, ...]) -> tuple[AuthUser, ...]:
    """Hash development passwords once per configuration, never per token check."""
    if raw:
        try:
            payload = json.loads(raw)
            if not isinstance(payload, dict) or not payload:
                return ()
            if any(
                not isinstance(config, dict)
                or not _canonical_identifier(username)
                or username.rsplit(".", 1)[-1].casefold() == "shared"
                or not _canonical_identifier(config.get("team_id", "default-team"))
                or config.get("role", "analyst") not in {"admin", "analyst", "viewer"}
                or not (config.get("password_hash") or config.get("password"))
                or (production and not _valid_password_hash(config.get("password_hash")))
                for username, config in payload.items()
            ):
                return ()
            shared_ids = {team_workspace_id(config.get("team_id", "default-team")) for config in payload.values()}
            personal_ids: set[str] = set()
            for username, config in payload.items():
                identity = build_user_session(username, config.get("team_id", "default-team"), config.get("role", "analyst"))
                workspace = identity["workspace_id"]
                if workspace in personal_ids or workspace in shared_ids:
                    return ()
                personal_ids.add(workspace)
            return tuple(
                AuthUser(
                    username=username,
                    password_hash=str(
                        config.get("password_hash") or hash_password(str(config.get("password", "")))
                    ),
                    display_name=str(config.get("display_name", username)),
                    team_id=str(config.get("team_id", "default-team")),
                    role=str(config.get("role", "analyst")),
                    credential_fingerprint=_credential_fingerprint(
                        "password_hash" if config.get("password_hash") else "password",
                        str(config.get("password_hash") or config.get("password", "")),
                    ),
                )
                for username, config in payload.items()
            )
        except (json.JSONDecodeError, TypeError, ValueError):
            return ()
    if production:
        return ()
    return tuple(
        AuthUser(username, hash_password(password), display_name, role=username,
                 credential_fingerprint=_credential_fingerprint("password", password))
        for username, password, display_name in zip(
            ("admin", "analyst", "viewer"), development_passwords,
            ("Admin Operator", "Analytics Operator", "Workspace Viewer"),
        )
    )


def configured_users() -> dict[str, AuthUser]:
    users = _configured_user_snapshot(
        os.getenv("AUTH_USERS", "").strip(),
        os.getenv("APP_ENV", "development").strip().lower() == "production",
        tuple(os.getenv(f"AUTH_{role.upper()}_PASSWORD", f"{role}123") for role in ("admin", "analyst", "viewer")),
    )
    return {user.username: user for user in users}


def _auth_fingerprint(user: AuthUser) -> str:
    encoded = json.dumps([
        "analytics-auth-v1", user.username, user.team_id, user.role, user.display_name, user.credential_fingerprint,
    ], separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def authenticate_user(username: str, password: str) -> AuthUser | None:
    user = configured_users().get(username.strip())
    if not user or not verify_password(password, user.password_hash):
        return None
    return user


def hash_password(password: str, *, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120_000)
    return f"pbkdf2_sha256$120000${salt}${digest.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, iterations, salt, expected = password_hash.split("$", 3)
    except ValueError:
        return secrets.compare_digest(password_hash, password)
    if algorithm != "pbkdf2_sha256":
        return False
    try:
        rounds = int(iterations)
        if rounds < 1 or rounds > 1_000_000:
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), rounds)
    except (ValueError, OverflowError):
        return False
    return secrets.compare_digest(digest.hex(), expected)


def _valid_password_hash(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        algorithm, rounds, salt, digest = value.split("$", 3)
        return (
            algorithm == "pbkdf2_sha256"
            and 120_000 <= int(rounds) <= 1_000_000
            and len(salt) >= 16
            and len(digest) == 64
            and len(bytes.fromhex(digest)) == 32
        )
    except ValueError:
        return False


def validate_auth_config() -> dict[str, Any]:
    users = configured_users()
    session_path = AUTH_SESSION_PATH
    warnings = []
    errors = []
    if not users:
        errors.append(
            "No valid auth users are configured. Use canonical, noncolliding user/team IDs; 'shared' is reserved. "
            "Production requires explicit AUTH_USERS with password hashes."
        )
    if os.getenv("APP_ENV", "development").strip().lower() != "production" and not os.getenv("AUTH_USERS"):
        warnings.append("Development demo accounts are enabled; configure AUTH_USERS before deployment.")
    return {
        "user_count": len(users),
        "session_ttl_hours": SESSION_TTL_HOURS,
        "session_path": str(session_path),
        "session_path_parent_exists": session_path.parent.exists(),
        "session_storage": "database",
        "file_fallback_enabled": False,
        "supports_password_hashes": True,
        "warnings": warnings,
        "errors": errors,
        "valid": not errors,
    }


def create_session(user: AuthUser) -> AuthSession:
    current = configured_users().get(user.username)
    if current is None or not secrets.compare_digest(_auth_fingerprint(user), _auth_fingerprint(current)):
        raise PersistenceError("Authentication configuration changed. Please sign in again.")
    user = current
    now = datetime.now(timezone.utc)
    identity = build_user_session(user.username, user.team_id, user.role, display_name=user.display_name)
    session = AuthSession(
        session_token=f"sess_{secrets.token_urlsafe(24)}",
        user_id=identity["user_id"],
        display_name=identity["display_name"],
        team_id=identity["team_id"],
        workspace_id=identity["workspace_id"],
        role=identity["role"],
        created_at=now.isoformat(),
        expires_at=(now + timedelta(hours=SESSION_TTL_HOURS)).isoformat(),
        auth_fingerprint=_auth_fingerprint(user),
    )
    try:
        build_auth_session_repository().create_session(session.session_token, asdict(session))
    except Exception as exc:
        raise PersistenceError("Authentication session could not be persisted") from exc
    _save_user(user)
    return session


def login_user(username: str, password: str) -> dict[str, Any] | None:
    user = authenticate_user(username, password)
    if user is None:
        return None
    return create_session(user).as_identity()


def validate_session_token(session_token: str | None) -> dict[str, Any] | None:
    """Read one token without rewriting a snapshot that could restore revoked sessions."""
    if not session_token:
        return None
    try:
        repository = build_auth_session_repository()
        payload = repository.get_session(session_token)
        if not payload or payload.get("session_token") != session_token:
            return None
        session = AuthSession(**payload)
        expires_at = datetime.fromisoformat(session.expires_at)
        if expires_at.tzinfo is None or expires_at <= datetime.now(timezone.utc):
            return None
        user = configured_users().get(session.user_id)
        if user is None or not session.auth_fingerprint or not secrets.compare_digest(
            session.auth_fingerprint, _auth_fingerprint(user),
        ):
            repository.delete_session(session_token)
            return None
        expected = build_user_session(user.username, user.team_id, user.role, display_name=user.display_name)
        if any(getattr(session, name) != expected[name] for name in (
            "user_id", "team_id", "workspace_id", "role", "display_name",
        )):
            repository.delete_session(session_token)
            return None
        return session.as_identity()
    except Exception:
        # The configured database is authoritative; stale JSON files must never
        # grant access when it is unavailable or contains malformed session data.
        return None


def revoke_session(session_token: str | None) -> bool:
    try:
        return revoke_session_checked(session_token)
    except PersistenceError:
        return False


def revoke_session_checked(session_token: str | None) -> bool:
    """Confirm server-side revocation; an absent token is already signed out."""
    if not session_token:
        return False
    try:
        return build_auth_session_repository().delete_session(session_token)
    except Exception as exc:
        raise PersistenceError("Sign-out could not be confirmed because session storage is unavailable.") from exc


def _save_user(user: AuthUser) -> None:
    try:
        build_auth_session_repository().save_user(user.username, {
            "username": user.username, "display_name": user.display_name, "team_id": user.team_id, "role": user.role,
        })
    except Exception:
        return


__all__ = [
    "AuthSession",
    "AuthUser",
    "authenticate_user",
    "configured_users",
    "create_session",
    "hash_password",
    "login_user",
    "revoke_session",
    "revoke_session_checked",
    "validate_auth_config",
    "validate_session_token",
    "verify_password",
]
