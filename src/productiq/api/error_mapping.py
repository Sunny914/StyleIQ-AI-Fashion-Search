"""Map exceptions to API errors for the HTTP layer (Phase 13.2)."""

from __future__ import annotations

from productiq.api.exceptions import ApiNotFoundError
from productiq.exceptions.base import CatalogValidationError
from productiq.serving.errors import (
    ApiErrorBody,
    ApiErrorCode,
    map_exception_to_api_error,
    safe_client_message,
)
from productiq.serving.product_service import ProductNotFoundError

_MISSING_SEED_PREFIX = "catalog row missing for seed product_id"


def is_missing_seed_product_error(exc: CatalogValidationError) -> bool:
    return _MISSING_SEED_PREFIX in str(exc).lower()


def map_http_exception_to_api_error(
    exc: BaseException,
    *,
    request_id: str | None = None,
) -> ApiErrorBody:
    if isinstance(exc, ApiNotFoundError):
        message = safe_client_message(exc)
        return ApiErrorBody(code=ApiErrorCode.NOT_FOUND, message=message, request_id=request_id)
    if isinstance(exc, ProductNotFoundError):
        return ApiErrorBody(
            code=ApiErrorCode.NOT_FOUND,
            message="Product not found.",
            request_id=request_id,
        )
    if isinstance(exc, CatalogValidationError) and is_missing_seed_product_error(exc):
        return ApiErrorBody(
            code=ApiErrorCode.NOT_FOUND,
            message="Seed product not found",
            request_id=request_id,
        )
    return map_exception_to_api_error(exc, request_id=request_id)


__all__ = ["is_missing_seed_product_error", "map_http_exception_to_api_error"]
