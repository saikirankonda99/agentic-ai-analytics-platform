from __future__ import annotations

import json
import os
import secrets
import hashlib
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from workspace import build_user_session


SESSION_TTL_HOURS = max(1, int(os.getenv("AUTH_SESSION_TTL_HOURS", "12")))
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
    if raw:
        try:
            payload = json.loads(raw)
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
        except json.JSONDecodeError:
            pass
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
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), int(iterations))
    return secrets.compare_digest(digest.hex(), expected)


def validate_auth_config() -> dict[str, Any]:
    users = configured_users()
    session_path = AUTH_SESSION_PATH
    warnings = []
    if not users:
        warnings.append("No local auth users are configured.")
    if os.getenv("APP_ENV") == "production" and not os.getenv("AUTH_USERS"):
        warnings.append("Production deployments should configure AUTH_USERS with password_hash values.")
    return {
        "user_count": len(users),
        "session_ttl_hours": SESSION_TTL_HOURS,
        "session_path": str(session_path),
        "session_path_parent_exists": session_path.parent.exists(),
        "supports_password_hashes": True,
        "warnings": warnings,
        "valid": not warnings,
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
    sessions = _load_sessions()
    sessions[session.session_token] = asdict(session)
    _save_sessions(_prune_expired(sessions))
    return session


def login_user(username: str, password: str) -> dict[str, Any] | None:
    user = authenticate_user(username, password)
    if user is None:
        return None
    return create_session(user).as_identity()


def validate_session_token(session_token: str | None) -> dict[str, Any] | None:
    if not session_token:
        return None
    sessions = _prune_expired(_load_sessions())
    payload = sessions.get(session_token)
    _save_sessions(sessions)
    if not payload:
        return None
    return AuthSession(**payload).as_identity()


def revoke_session(session_token: str | None) -> bool:
    if not session_token:
        return False
    sessions = _load_sessions()
    existed = session_token in sessions
    sessions.pop(session_token, None)
    _save_sessions(sessions)
    return existed


def _load_sessions() -> dict[str, dict[str, Any]]:
    try:
        return json.loads(AUTH_SESSION_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _save_sessions(sessions: dict[str, dict[str, Any]]) -> None:
    AUTH_SESSION_PATH.parent.mkdir(parents=True, exist_ok=True)
    AUTH_SESSION_PATH.write_text(json.dumps(sessions, indent=2), encoding="utf-8")


def _prune_expired(sessions: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    now = datetime.now(timezone.utc)
    active = {}
    for token, payload in sessions.items():
        try:
            expires_at = datetime.fromisoformat(str(payload.get("expires_at")))
        except ValueError:
            continue
        if expires_at > now:
            active[token] = payload
    return active


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
