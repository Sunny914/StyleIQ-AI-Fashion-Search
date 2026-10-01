"""Observability metrics contract (Phase 13.9.1).

Defines stable metric names and bounded label dimensions. Exporters/backends are
deferred to later sub-phases.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from productiq.exceptions.base import ValidationError

HIGH_CARDINALITY_LABEL_KEYS = frozenset(
    {
        "request_id",
        "product_id",
        "seed_product_id",
        "query",
        "user_id",
        "session_id",
        "exception",
        "error_message",
        "trace_id",
        "span_id",
    },
)


class MetricName(StrEnum):
    API_REQUESTS_TOTAL = "productiq_api_requests_total"
    API_REQUEST_DURATION_MS = "productiq_api_request_duration_ms"
    API_ERRORS_TOTAL = "productiq_api_errors_total"
    SEARCH_REQUESTS_TOTAL = "productiq_search_requests_total"
    SEARCH_DURATION_MS = "productiq_search_duration_ms"
    RECOMMENDATION_REQUESTS_TOTAL = "productiq_recommendation_requests_total"
    RECOMMENDATION_DURATION_MS = "productiq_recommendation_duration_ms"
    PRODUCT_REQUESTS_TOTAL = "productiq_product_requests_total"
    PRODUCT_DURATION_MS = "productiq_product_duration_ms"


METRIC_ALLOWED_LABELS: dict[str, frozenset[str]] = {
    MetricName.API_REQUESTS_TOTAL: frozenset({"endpoint", "operation", "status_class", "outcome"}),
    MetricName.API_REQUEST_DURATION_MS: frozenset({"endpoint", "operation", "status_class"}),
    MetricName.API_ERRORS_TOTAL: frozenset({"endpoint", "operation", "error_code"}),
    MetricName.SEARCH_REQUESTS_TOTAL: frozenset({"operation", "outcome"}),
    MetricName.SEARCH_DURATION_MS: frozenset({"operation", "outcome"}),
    MetricName.RECOMMENDATION_REQUESTS_TOTAL: frozenset(
        {"operation", "outcome", "recommendation_type"},
    ),
    MetricName.RECOMMENDATION_DURATION_MS: frozenset(
        {"operation", "outcome", "recommendation_type"},
    ),
    MetricName.PRODUCT_REQUESTS_TOTAL: frozenset({"operation", "outcome"}),
    MetricName.PRODUCT_DURATION_MS: frozenset({"operation", "outcome"}),
}


class MetricObservation(BaseModel):
    """In-process metric observation contract (not tied to Prometheus yet)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: MetricName
    value: float
    labels: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def check_labels(self) -> MetricObservation:
        validate_metric_labels(self.name, self.labels)
        return self


def validate_metric_labels(metric_name: MetricName | str, labels: dict[str, str]) -> None:
    resolved = MetricName(metric_name) if isinstance(metric_name, str) else metric_name
    allowed = METRIC_ALLOWED_LABELS.get(resolved)
    if allowed is None:
        msg = f"unknown metric name: {resolved}"
        raise ValidationError(msg)
    for key in labels:
        if key in HIGH_CARDINALITY_LABEL_KEYS:
            msg = f"high-cardinality label {key!r} is not permitted"
            raise ValidationError(msg)
        if key not in allowed:
            msg = f"label {key!r} is not allowed for metric {resolved.value}"
            raise ValidationError(msg)


__all__ = [
    "HIGH_CARDINALITY_LABEL_KEYS",
    "METRIC_ALLOWED_LABELS",
    "MetricName",
    "MetricObservation",
    "validate_metric_labels",
]
