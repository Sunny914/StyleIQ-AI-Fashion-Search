"""HTTP resilience middleware (Phase 13.10-B)."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from productiq.api.middleware.observability import resolve_api_operation
from productiq.serving.config import ServingConfig
from productiq.serving.errors import ApiErrorBody, ApiErrorCode, ApiErrorEnvelope
from productiq.serving.resilience.concurrency import ConcurrencyGate, NullConcurrencyGate
from productiq.serving.resilience.keys import build_rate_limit_key
from productiq.serving.resilience.wiring import ApplicationResilience


def _error_response(
    *,
    code: ApiErrorCode,
    message: str,
    request: Request,
    retry_after: int | None = None,
) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    envelope = ApiErrorEnvelope(
        error=ApiErrorBody(code=code, message=message, request_id=request_id),
    )
    from productiq.api.http_status import http_status_for_api_error

    status = http_status_for_api_error(code)
    headers: dict[str, str] = {}
    if retry_after is not None and code is ApiErrorCode.RATE_LIMITED:
        headers["Retry-After"] = str(retry_after)
    return JSONResponse(status_code=status, content=envelope.model_dump(mode="json"), headers=headers)


def _should_protect(operation: str) -> bool:
    return operation in {"search", "recommendation", "product"}


class ResilienceMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        config: ServingConfig = request.app.state.serving_config
        resilience: ApplicationResilience = request.app.state.application_resilience
        operation, route, _method = resolve_api_operation(request)

        if operation in {"health"} or route.endswith("/ready"):
            return await call_next(request)

        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                body_size = int(content_length)
            except ValueError:
                body_size = 0
            if body_size > config.api_max_body_bytes:
                return _error_response(
                    code=ApiErrorCode.INVALID_REQUEST,
                    message="Request body too large",
                    request=request,
                )

        if _should_protect(operation):
            key = build_rate_limit_key(
                request,
                deployment_key=config.rate_limit_deployment_key,
                trust_forwarded_for=config.rate_limit_trust_forwarded_for,
            )
            decision = resilience.rate_limiter.allow(key)
            if not decision.allowed:
                return _error_response(
                    code=ApiErrorCode.RATE_LIMITED,
                    message="Rate limit exceeded",
                    request=request,
                    retry_after=decision.retry_after_seconds,
                )

        gate = _concurrency_gate(resilience, operation)
        acquired = False
        if isinstance(gate, ConcurrencyGate):
            acquired = gate.try_acquire()
            if not acquired:
                return _error_response(
                    code=ApiErrorCode.OVERLOADED,
                    message="Service is temporarily overloaded",
                    request=request,
                )

        timeout = config.serving_request_timeout_seconds
        try:
            if timeout > 0:
                response = await asyncio.wait_for(call_next(request), timeout=timeout)
            else:
                response = await call_next(request)
        except TimeoutError:
            return _error_response(
                code=ApiErrorCode.SERVICE_UNAVAILABLE,
                message="Request timed out",
                request=request,
            )
        finally:
            if acquired and isinstance(gate, ConcurrencyGate):
                gate.release()
        return response


def _concurrency_gate(
    resilience: ApplicationResilience,
    operation: str,
) -> ConcurrencyGate | NullConcurrencyGate:
    if operation == "search":
        return resilience.search_concurrency
    if operation == "recommendation":
        return resilience.recommendation_concurrency
    return NullConcurrencyGate()


__all__ = ["ResilienceMiddleware"]
