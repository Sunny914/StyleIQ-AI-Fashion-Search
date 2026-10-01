"""HTTP observability middleware (Phase 13.9-B)."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from productiq.observability.runtime.emitter import (
    api_error_code_from_http_status,
    bind_observability_sink,
    emit_api_request_completed,
    emit_api_request_failed,
    emit_api_request_started,
    reset_observability_sink,
)
from productiq.observability.runtime.sink import NullObservabilitySink, ObservabilitySink
from productiq.serving.versioning import SERVING_API_ROUTE_PREFIX


def resolve_api_operation(request: Request) -> tuple[str, str, str]:
    path = request.url.path
    method = request.method.upper()
    if path.endswith(f"{SERVING_API_ROUTE_PREFIX}/search") and method == "POST":
        return "search", path, method
    if path.endswith(f"{SERVING_API_ROUTE_PREFIX}/recommendations") and method == "POST":
        return "recommendation", path, method
    if f"{SERVING_API_ROUTE_PREFIX}/products/" in path and method == "GET":
        return "product", path, method
    if path.endswith(f"{SERVING_API_ROUTE_PREFIX}/health") and method == "GET":
        return "health", path, method
    return "api", path, method


class ObservabilityMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        sink: ObservabilitySink = getattr(
            request.app.state,
            "observability_sink",
            NullObservabilitySink(),
        )
        token = bind_observability_sink(sink)
        operation, route, method = resolve_api_operation(request)
        start = time.perf_counter()
        emit_api_request_started(operation=operation, route=route, http_method=method)
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = (time.perf_counter() - start) * 1000.0
            emit_api_request_failed(
                operation=operation,
                route=route,
                http_method=method,
                duration_ms=duration_ms,
                error_code=api_error_code_from_http_status(500),
            )
            reset_observability_sink(token)
            raise
        duration_ms = (time.perf_counter() - start) * 1000.0
        emit_api_request_completed(
            operation=operation,
            route=route,
            http_method=method,
            status_code=response.status_code,
            duration_ms=duration_ms,
        )
        reset_observability_sink(token)
        return response


__all__ = ["ObservabilityMiddleware", "resolve_api_operation"]
