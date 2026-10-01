"""Map API error codes to HTTP status codes (Phase 13.2)."""

from __future__ import annotations

from productiq.serving.errors import ApiErrorCode

HTTP_STATUS_BY_API_ERROR: dict[ApiErrorCode, int] = {
    ApiErrorCode.INVALID_REQUEST: 400,
    ApiErrorCode.NOT_FOUND: 404,
    ApiErrorCode.CONFIGURATION_ERROR: 503,
    ApiErrorCode.SERVICE_UNAVAILABLE: 503,
    ApiErrorCode.INTERNAL_ERROR: 500,
    ApiErrorCode.RATE_LIMITED: 429,
    ApiErrorCode.OVERLOADED: 503,
}


def http_status_for_api_error(code: ApiErrorCode) -> int:
    return HTTP_STATUS_BY_API_ERROR[code]


__all__ = [
    "HTTP_STATUS_BY_API_ERROR",
    "http_status_for_api_error",
]
