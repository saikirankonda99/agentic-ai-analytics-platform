from __future__ import annotations

from fastapi import Header

from backend.models import DEFAULT_USER_ID, DEFAULT_WORKSPACE_ID, RequestSession, User, Workspace


def get_request_session(
    x_user_id: str | None = Header(default=None),
    x_workspace_id: str | None = Header(default=None),
) -> RequestSession:
    user_id = x_user_id or DEFAULT_USER_ID
    workspace_id = x_workspace_id or DEFAULT_WORKSPACE_ID
    return RequestSession(
        user=User(user_id=user_id),
        workspace=Workspace(workspace_id=workspace_id, name=workspace_id.removeprefix("workspace:")),
        roles=("workspace:member",),
    )


__all__ = ["get_request_session"]
