"""Correlate requests via X-Request-ID (Phase 13.2)."""

from __future__ import annotations

import re
import uuid
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from productiq.api.context import clear_request_id, set_request_id

REQUEST_ID_HEADER = "X-Request-ID"
MAX_REQUEST_ID_LENGTH = 128
_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]+$")


def normalize_request_id(raw: str | None) -> str:
    """Accept a client id when safe; otherwise generate a new UUID."""
    if raw is None:
        return str(uuid.uuid4())
    candidate = raw.strip()
    if not candidate or len(candidate) > MAX_REQUEST_ID_LENGTH:
        return str(uuid.uuid4())
    if not _SAFE_REQUEST_ID.fullmatch(candidate):
        return str(uuid.uuid4())
    return candidate


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = normalize_request_id(request.headers.get(REQUEST_ID_HEADER))
        request.state.request_id = request_id
        set_request_id(request_id)
        try:
            response = await call_next(request)
        finally:
            clear_request_id()
        response.headers[REQUEST_ID_HEADER] = request_id
        return response


__all__ = [
    "MAX_REQUEST_ID_LENGTH",
    "REQUEST_ID_HEADER",
    "RequestIdMiddleware",
    "normalize_request_id",
]



