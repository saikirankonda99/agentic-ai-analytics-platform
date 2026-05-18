from __future__ import annotations

from fastapi import Header

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
    x_user_id: str | None = Header(default=None),
    x_organization_id: str | None = Header(default=None),
    x_workspace_id: str | None = Header(default=None),
) -> RequestSession:
    user_id = x_user_id or DEFAULT_USER_ID
    organization_id = x_organization_id or DEFAULT_ORGANIZATION_ID
    workspace_id = x_workspace_id or DEFAULT_WORKSPACE_ID
    roles = ("workspace:member",)
    return RequestSession(
        user=User(user_id=user_id),
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
