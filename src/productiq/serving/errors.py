"""API error envelope and ProductIQ exception mapping (Phase 13.1)."""

from __future__ import annotations

import re
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from productiq.exceptions.base import (
    CatalogLoadError,
    CatalogValidationError,
    ConfigurationError,
    DatabaseError,
    ProductIQError,
    QueryRepresentationError,
    RankingError,
    RecommendationError,
    RetrievalError,
    ValidationError,
)


class ApiErrorCode(StrEnum):
    """Stable public error codes for HTTP clients."""

    INVALID_REQUEST = "INVALID_REQUEST"
    NOT_FOUND = "NOT_FOUND"
    CONFIGURATION_ERROR = "CONFIGURATION_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    RATE_LIMITED = "RATE_LIMITED"
    OVERLOADED = "OVERLOADED"


class ApiErrorBody(BaseModel):
    """Single error object returned to API clients."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    code: ApiErrorCode
    message: str = Field(min_length=1)
    request_id: str | None = Field(
        default=None,
        description="Correlation id for support; never substitute for authentication.",
    )


class ApiErrorEnvelope(BaseModel):
    """Top-level JSON error shape for failed API requests."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    error: ApiErrorBody


_CLIENT_MESSAGE_MAX_LEN = 240
_REDACTED = "[redacted]"
_CREDENTIAL_URL = re.compile(r"(postgresql|postgres|mysql|mongodb)://[^\s]+", re.IGNORECASE)
_BEARER = re.compile(r"Bearer\s+\S+", re.IGNORECASE)
_FILE_PATH = re.compile(r"(?:[A-Za-z]:\\|/)[^\s\"']+")


def _sanitize_client_text(text: str) -> str:
    cleaned = _CREDENTIAL_URL.sub(_REDACTED, text)
    cleaned = _BEARER.sub("Bearer [redacted]", cleaned)
    cleaned = _FILE_PATH.sub(_REDACTED, cleaned)
    if "traceback" in cleaned.lower() or "stack trace" in cleaned.lower():
        return "An unexpected error occurred"
    cleaned = cleaned.strip()
    if len(cleaned) > _CLIENT_MESSAGE_MAX_LEN:
        return cleaned[: _CLIENT_MESSAGE_MAX_LEN - 3] + "..."
    return cleaned


def safe_client_message(exc: BaseException) -> str:
    """Return a client-safe message without stack traces or Python repr noise."""
    if isinstance(exc, ProductIQError):
        text = str(exc).strip()
        if not text:
            return exc.__class__.__name__
        return _sanitize_client_text(text)
    if isinstance(exc, ValueError):
        text = str(exc).strip()
        if not text:
            return "Invalid request"
        return _sanitize_client_text(text)
    return "An unexpected error occurred"


def map_exception_to_api_error(
    exc: BaseException,
    *,
    request_id: str | None = None,
) -> ApiErrorBody:
    """Map domain exceptions to the public API error model."""
    message = safe_client_message(exc)
    if isinstance(exc, (ValueError, QueryRepresentationError)):
        code = ApiErrorCode.INVALID_REQUEST
    elif isinstance(exc, (RetrievalError, RankingError, RecommendationError)):
        code = ApiErrorCode.INTERNAL_ERROR
    elif isinstance(exc, ValidationError):
        code = ApiErrorCode.INVALID_REQUEST
    elif isinstance(exc, ConfigurationError):
        code = ApiErrorCode.CONFIGURATION_ERROR
    elif isinstance(exc, (DatabaseError, CatalogLoadError, CatalogValidationError)):
        code = ApiErrorCode.SERVICE_UNAVAILABLE
    elif isinstance(exc, ProductIQError):
        code = ApiErrorCode.INTERNAL_ERROR
    else:
        code = ApiErrorCode.INTERNAL_ERROR
        message = "An unexpected error occurred"
    return ApiErrorBody(code=code, message=_sanitize_client_text(message), request_id=request_id)


__all__ = [
    "ApiErrorBody",
    "ApiErrorCode",
    "ApiErrorEnvelope",
    "map_exception_to_api_error",
    "safe_client_message",
]
