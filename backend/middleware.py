from __future__ import annotations

from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from fastapi import HTTPException

from backend.auth_context import session_from_token
from backend.models import DEFAULT_ORGANIZATION_ID, DEFAULT_USER_ID, DEFAULT_WORKSPACE_ID
from backend.usage import UsageService, usage_service


class RequestContextMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: object, usage: UsageService = usage_service) -> None:
        super().__init__(app)
        self.usage = usage

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        authorization = request.headers.get("authorization", "")
        token = request.headers.get("x-session-token") or (
            authorization.removeprefix("Bearer ").strip() if authorization.startswith("Bearer ") else None
        )
        try:
            session = session_from_token(token)
        except HTTPException:
            session = None
        user_id = session.user_id if session else DEFAULT_USER_ID
        organization_id = session.organization_id if session else DEFAULT_ORGANIZATION_ID
        workspace_id = session.workspace_id if session else DEFAULT_WORKSPACE_ID
        request.state.user_id = user_id
        request.state.organization_id = organization_id
        request.state.workspace_id = workspace_id

        response = await call_next(request)
        self.usage.record(
            "api_request",
            organization_id=organization_id,
            workspace_id=workspace_id,
            user_id=user_id,
            metadata={
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
            },
        )
        return response


__all__ = ["RequestContextMiddleware"]
