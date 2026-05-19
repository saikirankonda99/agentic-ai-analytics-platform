from __future__ import annotations

from fastapi import Header

from backend.auth_sessions import validate_session_token
from backend.models import (
    DEFAULT_ORGANIZATION_ID,
    DEFAULT_USER_ID,
    DEFAULT_WORKSPACE_ID,
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
    user_id_header = x_user_id if isinstance(x_user_id, str) else None
    organization_id_header = x_organization_id if isinstance(x_organization_id, str) else None
    workspace_id_header = x_workspace_id if isinstance(x_workspace_id, str) else None
    bearer_token = (
        authorization_value.removeprefix("Bearer ").strip()
        if authorization_value and authorization_value.startswith("Bearer ")
        else None
    )
    identity = validate_session_token(session_token_value or bearer_token)
    user_id = (identity or {}).get("user_id") or user_id_header or DEFAULT_USER_ID
    organization_id = organization_id_header or DEFAULT_ORGANIZATION_ID
    workspace_id = (identity or {}).get("workspace_id") or workspace_id_header or DEFAULT_WORKSPACE_ID
    role = (identity or {}).get("role", "member")
    roles = (f"workspace:{role}", "workspace:member")
    return RequestSession(
        user=User(user_id=user_id, display_name=(identity or {}).get("display_name")),
        organization=Organization(
            organization_id=organization_id,
            name=organization_id.removeprefix("organization:"),
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


__all__ = ["get_request_session"]
