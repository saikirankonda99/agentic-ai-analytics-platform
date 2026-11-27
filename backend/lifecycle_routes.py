from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.auth_context import get_request_session
from backend.data_lifecycle import delete_workspace_data
from backend.models import RequestSession
from backend.persistence import PersistenceError
from workspace import build_user_session


router = APIRouter(tags=["workspace data"])


@router.delete("/workspaces/{workspace_id}/data")
def delete_data(
    workspace_id: str, confirm: bool = Query(False), session: RequestSession = Depends(get_request_session),
) -> dict:
    if not confirm:
        raise HTTPException(status_code=400, detail="Explicit confirmation is required: confirm=true")
    role = next((name for name in ("admin", "analyst", "viewer") if f"workspace:{name}" in session.roles), "viewer")
    identity = build_user_session(session.user_id, session.organization.name, role, session.user.display_name)
    identity["workspace_id"] = workspace_id
    try:
        counts = delete_workspace_data(identity)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail="Workspace deletion is not allowed for this identity") from exc
    except PersistenceError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"status": "deleted", "workspace_id": workspace_id, "deleted_records": counts,
            "accounts_retained": True, "backups_retained": True}
