"""Request-scoped observability context (Phase 13.9.1).

Integrates with the existing API request ID (``productiq.api.context``); does not
introduce a second request-ID mechanism.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field, field_validator

from productiq.observability.versioning import OBSERVABILITY_CONTRACT_VERSION

DEFAULT_SERVICE_NAME = "productiq"

_MAX_CORRELATION_ID_LENGTH = 128
_SAFE_CORRELATION = re.compile(r"^[A-Za-z0-9._-]+$")


class ObservabilityContext(BaseModel):
    """Correlation context carried across API, serving, and domain layers."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    contract_version: str = Field(default=OBSERVABILITY_CONTRACT_VERSION, min_length=1)
    request_id: str | None = Field(
        default=None,
        description="Populated from API middleware when handling HTTP requests.",
    )
    service_name: str = Field(default=DEFAULT_SERVICE_NAME, min_length=1)
    operation: str = Field(min_length=1)
    correlation_id: str | None = Field(
        default=None,
        description="Optional bounded secondary correlation (not a replacement for request_id).",
    )

    @field_validator("correlation_id")
    @classmethod
    def validate_correlation_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        candidate = value.strip()
        if not candidate or len(candidate) > _MAX_CORRELATION_ID_LENGTH:
            msg = "correlation_id must be non-empty and bounded"
            raise ValueError(msg)
        if not _SAFE_CORRELATION.fullmatch(candidate):
            msg = "correlation_id contains disallowed characters"
            raise ValueError(msg)
        return candidate


def build_observability_context(
    *,
    operation: str,
    service_name: str = DEFAULT_SERVICE_NAME,
    request_id: str | None = None,
    correlation_id: str | None = None,
) -> ObservabilityContext:
    """Build context; default ``request_id`` from API contextvar when omitted."""
    from productiq.api.context import get_request_id

    resolved_request_id = request_id if request_id is not None else get_request_id()
    return ObservabilityContext(
        service_name=service_name,
        operation=operation,
        request_id=resolved_request_id,
        correlation_id=correlation_id,
    )


__all__ = [
    "DEFAULT_SERVICE_NAME",
    "ObservabilityContext",
    "build_observability_context",
]
