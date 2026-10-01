"""Observability event contract (Phase 13.9.1)."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from productiq.exceptions.base import ValidationError
from productiq.observability.versioning import OBSERVABILITY_CONTRACT_VERSION
from productiq.serving.errors import ApiErrorCode

PROHIBITED_METADATA_KEYS = frozenset(
    {
        "api_key",
        "password",
        "token",
        "authorization",
        "cookie",
        "set_cookie",
        "database_url",
        "connection_string",
        "embedding",
        "embeddings",
        "query",
        "search_query",
        "request_body",
        "headers",
        "exception",
        "stack_trace",
        "traceback",
    },
)

ALLOWED_METADATA_KEYS = frozenset(
    {
        "http_method",
        "route",
        "status_code",
        "status_class",
        "endpoint",
        "operation",
        "outcome",
        "result_count",
        "candidate_count",
        "top_k",
        "query_length",
        "filter_count",
        "recommendation_type",
        "duration_ms",
        "layer",
    },
)


class ObservabilityOutcome(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"


class ObservabilityEventName(StrEnum):
    API_REQUEST_STARTED = "api.request.started"
    API_REQUEST_COMPLETED = "api.request.completed"
    API_REQUEST_FAILED = "api.request.failed"
    SEARCH_REQUEST_COMPLETED = "search.request.completed"
    RECOMMENDATION_REQUEST_COMPLETED = "recommendation.request.completed"
    PRODUCT_REQUEST_COMPLETED = "product.request.completed"
    RETRIEVAL_COMPLETED = "retrieval.completed"
    RANKING_COMPLETED = "ranking.completed"
    RECOMMENDATION_GENERATION_COMPLETED = "recommendation.generation.completed"


REGISTERED_EVENT_NAMES = frozenset(name.value for name in ObservabilityEventName)


class ObservabilityEvent(BaseModel):
    """Vendor-neutral structured observability event (log-oriented contract)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    contract_version: str = Field(default=OBSERVABILITY_CONTRACT_VERSION, min_length=1)
    timestamp_utc: datetime
    event_name: ObservabilityEventName
    request_id: str | None = None
    service_name: str = Field(min_length=1)
    operation: str = Field(min_length=1)
    outcome: ObservabilityOutcome | None = None
    duration_ms: float | None = Field(default=None, ge=0.0)
    error_code: ApiErrorCode | None = None
    metadata: dict[str, str | int | float | bool] = Field(default_factory=dict)

    @field_validator("metadata")
    @classmethod
    def validate_metadata_keys(
        cls,
        metadata: dict[str, str | int | float | bool],
    ) -> dict[str, str | int | float | bool]:
        validate_event_metadata(metadata)
        return metadata


def validate_event_metadata(metadata: dict[str, str | int | float | bool]) -> None:
    for key in metadata:
        normalized = key.lower().replace("-", "_")
        if normalized in PROHIBITED_METADATA_KEYS:
            msg = f"metadata key {key!r} is prohibited for privacy/security"
            raise ValidationError(msg)
        if key not in ALLOWED_METADATA_KEYS:
            msg = f"metadata key {key!r} is not in the observability allowlist"
            raise ValidationError(msg)


def assert_registered_event_name(name: str) -> ObservabilityEventName:
    try:
        return ObservabilityEventName(name)
    except ValueError as exc:
        msg = f"unregistered observability event name: {name!r}"
        raise ValidationError(msg) from exc


__all__ = [
    "ALLOWED_METADATA_KEYS",
    "PROHIBITED_METADATA_KEYS",
    "REGISTERED_EVENT_NAMES",
    "ObservabilityEvent",
    "ObservabilityEventName",
    "ObservabilityOutcome",
    "assert_registered_event_name",
    "validate_event_metadata",
]
