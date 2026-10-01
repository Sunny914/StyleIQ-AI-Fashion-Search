"""Trace/span contract (Phase 13.9.1).

Vendor-neutral span record only — OpenTelemetry/Prometheus integrations deferred.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from productiq.observability.versioning import OBSERVABILITY_CONTRACT_VERSION


class SpanKind(StrEnum):
    API = "api"
    SERVING = "serving"
    DOMAIN = "domain"


class ObservabilitySpan(BaseModel):
    """Logical span contract; not an OpenTelemetry span implementation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    contract_version: str = Field(default=OBSERVABILITY_CONTRACT_VERSION, min_length=1)
    span_name: str = Field(min_length=1)
    kind: SpanKind
    started_at_utc: datetime
    duration_ms: float = Field(ge=0.0)
    request_id: str | None = None
    operation: str | None = None
    parent_span_name: str | None = None


__all__ = ["ObservabilitySpan", "SpanKind"]
