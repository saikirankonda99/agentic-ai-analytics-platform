from __future__ import annotations

import json
import os
import secrets
import hashlib
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from backend.persistence import PersistenceError, build_auth_session_repository
from workspace import build_user_session


SESSION_TTL_HOURS = max(1, int(os.getenv("AUTH_SESSION_TTL_HOURS", "12")))
# Kept for diagnostics compatibility; session authentication never reads this legacy file.
AUTH_SESSION_PATH = Path(os.getenv("AUTH_SESSION_PATH", "data/auth_sessions.json"))


@dataclass(frozen=True)
class AuthUser:
    username: str
    password_hash: str
    display_name: str
    team_id: str = "default-team"
    role: str = "analyst"


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


def configured_users() -> dict[str, AuthUser]:
    raw = os.getenv("AUTH_USERS", "").strip()
    production = os.getenv("APP_ENV", "development").strip().lower() == "production"
    if raw:
        try:
            payload = json.loads(raw)
            if not isinstance(payload, dict) or not payload:
                return {}
            if any(
                not isinstance(config, dict)
                or config.get("role", "analyst") not in {"admin", "analyst", "viewer"}
                or not (config.get("password_hash") or config.get("password"))
                or (production and not _valid_password_hash(config.get("password_hash")))
                for config in payload.values()
            ):
                return {}
            return {
                username: AuthUser(
                    username=username,
                    password_hash=str(
                        config.get("password_hash") or hash_password(str(config.get("password", "")))
                    ),
                    display_name=str(config.get("display_name", username)),
                    team_id=str(config.get("team_id", "default-team")),
                    role=str(config.get("role", "analyst")),
                )
                for username, config in payload.items()
                if isinstance(config, dict)
            }
        except (json.JSONDecodeError, TypeError, ValueError):
            return {}
    if production:
        return {}
    return {
        "admin": AuthUser("admin", hash_password(os.getenv("AUTH_ADMIN_PASSWORD", "admin123")), "Admin Operator", role="admin"),
        "analyst": AuthUser(
            "analyst",
            hash_password(os.getenv("AUTH_ANALYST_PASSWORD", "analyst123")),
            "Analytics Operator",
            role="analyst",
        ),
        "viewer": AuthUser("viewer", hash_password(os.getenv("AUTH_VIEWER_PASSWORD", "viewer123")), "Workspace Viewer", role="viewer"),
    }


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
        errors.append("No valid auth users are configured; production requires explicit AUTH_USERS with password hashes.")
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
        payload = build_auth_session_repository().get_session(session_token)
        if not payload or payload.get("session_token") != session_token:
            return None
        session = AuthSession(**payload)
        expires_at = datetime.fromisoformat(session.expires_at)
        if expires_at.tzinfo is None or expires_at <= datetime.now(timezone.utc):
            return None
        return session.as_identity()
    except Exception:
        # The configured database is authoritative; stale JSON files must never
        # grant access when it is unavailable or contains malformed session data.
        return None


def revoke_session(session_token: str | None) -> bool:
    if not session_token:
        return False
    try:
        return build_auth_session_repository().delete_session(session_token)
    except Exception:
        return False


def _save_user(user: AuthUser) -> None:
    try:
        build_auth_session_repository().save_user(user.username, asdict(user))
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
    "validate_auth_config",
    "validate_session_token",
    "verify_password",
]
