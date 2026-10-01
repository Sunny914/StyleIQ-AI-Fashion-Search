"""Register stable API exception handlers (Phase 13.2)."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from productiq.api.error_mapping import map_http_exception_to_api_error
from productiq.api.http_status import http_status_for_api_error
from productiq.exceptions.base import ProductIQError
from productiq.serving.errors import ApiErrorBody, ApiErrorCode, ApiErrorEnvelope


def _request_id_from_request(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def _json_error_response(body: ApiErrorBody) -> JSONResponse:
    envelope = ApiErrorEnvelope(error=body)
    status = http_status_for_api_error(body.code)
    return JSONResponse(status_code=status, content=envelope.model_dump(mode="json"))


async def request_validation_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    _ = exc
    body = ApiErrorBody(
        code=ApiErrorCode.INVALID_REQUEST,
        message="Request validation failed",
        request_id=_request_id_from_request(request),
    )
    return _json_error_response(body)


async def productiq_error_handler(request: Request, exc: ProductIQError) -> JSONResponse:
    body = map_http_exception_to_api_error(
        exc,
        request_id=_request_id_from_request(request),
    )
    return _json_error_response(body)


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    _ = exc
    body = ApiErrorBody(
        code=ApiErrorCode.INTERNAL_ERROR,
        message="An unexpected error occurred",
        request_id=_request_id_from_request(request),
    )
    return _json_error_response(body)


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(RequestValidationError, request_validation_handler)  # type: ignore[arg-type]
    app.add_exception_handler(ProductIQError, productiq_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_exception_handler)


__all__ = [
    "productiq_error_handler",
    "register_exception_handlers",
    "request_validation_handler",
    "unhandled_exception_handler",
]
