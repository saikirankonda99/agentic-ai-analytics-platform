from __future__ import annotations

from fastapi import Header, HTTPException

from backend.auth_sessions import validate_session_token
from backend.models import (
    Organization,
    RequestSession,
    User,
    Workspace,
    WorkspaceMembership,
)


def get_request_session(
    authorization: str | None = Header(default=None),
    x_session_token: str | None = Header(default=None),
    x_user_id: str | None = Header(default=None),
    x_organization_id: str | None = Header(default=None),
    x_workspace_id: str | None = Header(default=None),
) -> RequestSession:
    authorization_value = authorization if isinstance(authorization, str) else None
    session_token_value = x_session_token if isinstance(x_session_token, str) else None
    bearer_token = (
        authorization_value.removeprefix("Bearer ").strip()
        if authorization_value and authorization_value.startswith("Bearer ")
        else None
    )
    return session_from_token(session_token_value or bearer_token)


def session_from_token(token: str | None) -> RequestSession:
    """Resolve identity only from a validated server-side session, including for websockets."""
    identity = validate_session_token(token)
    if not identity:
        raise HTTPException(status_code=401, detail="Authentication required", headers={"WWW-Authenticate": "Bearer"})
    user_id = identity["user_id"]
    team_id = identity["team_id"]
    organization_id = f"organization:{team_id}"
    workspace_id = identity["workspace_id"]
    role = identity["role"]
    roles = (f"workspace:{role}", "workspace:member")
    return RequestSession(
        user=User(user_id=user_id, display_name=identity.get("display_name")),
        organization=Organization(
            organization_id=organization_id,
            name=team_id,
        ),
        workspace=Workspace(
            workspace_id=workspace_id,
            name=workspace_id.removeprefix("workspace:"),
            organization_id=organization_id,
        ),
        membership=WorkspaceMembership(
            user_id=user_id,
            workspace_id=workspace_id,
            organization_id=organization_id,
            roles=roles,
        ),
        roles=roles,
    )


__all__ = ["get_request_session", "session_from_token"]
