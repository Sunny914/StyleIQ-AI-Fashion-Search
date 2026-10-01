"""Serving-layer telemetry helpers (Phase 13.9-B)."""

from __future__ import annotations

import time
from datetime import UTC, datetime

from productiq.observability.context import build_observability_context
from productiq.observability.events import (
    ObservabilityEvent,
    ObservabilityEventName,
    ObservabilityOutcome,
)
from productiq.observability.metrics import MetricName, MetricObservation
from productiq.observability.runtime.emitter import (
    record_event,
    record_metric,
    record_span,
    validate_event_metadata_safe,
)
from productiq.observability.tracing import ObservabilitySpan, SpanKind
from productiq.serving.errors import ApiErrorCode


def emit_search_request_completed(
    *,
    duration_ms: float,
    result_count: int,
    top_k: int,
    query_length: int,
    candidate_count: int | None = None,
) -> None:
    ctx = build_observability_context(operation="search")
    metadata: dict[str, str | int | float | bool] = {
        "result_count": result_count,
        "top_k": top_k,
        "query_length": query_length,
        "outcome": "success",
    }
    if candidate_count is not None:
        metadata["candidate_count"] = candidate_count
    record_event(
        ObservabilityEvent(
            timestamp_utc=datetime.now(tz=UTC),
            event_name=ObservabilityEventName.SEARCH_REQUEST_COMPLETED,
            request_id=ctx.request_id,
            service_name=ctx.service_name,
            operation="search",
            outcome=ObservabilityOutcome.SUCCESS,
            duration_ms=duration_ms,
            metadata=validate_event_metadata_safe(metadata),
        ),
    )
    record_metric(
        MetricObservation(
            name=MetricName.SEARCH_REQUESTS_TOTAL,
            value=1.0,
            labels={"operation": "search", "outcome": "success"},
        ),
    )
    record_metric(
        MetricObservation(
            name=MetricName.SEARCH_DURATION_MS,
            value=duration_ms,
            labels={"operation": "search", "outcome": "success"},
        ),
    )


def emit_search_stage_from_timings(
    *,
    retrieval_ms: float | None,
    ranking_ms: float | None,
    candidate_count: int | None,
    result_count: int,
) -> None:
    ctx = build_observability_context(operation="search")
    now = datetime.now(tz=UTC)
    if retrieval_ms is not None:
        metadata: dict[str, str | int | float | bool] = {"outcome": "success"}
        if candidate_count is not None:
            metadata["candidate_count"] = candidate_count
        record_event(
            ObservabilityEvent(
                timestamp_utc=now,
                event_name=ObservabilityEventName.RETRIEVAL_COMPLETED,
                request_id=ctx.request_id,
                service_name=ctx.service_name,
                operation="search",
                outcome=ObservabilityOutcome.SUCCESS,
                duration_ms=retrieval_ms,
                metadata=validate_event_metadata_safe(metadata),
            ),
        )
        record_span(
            ObservabilitySpan(
                span_name="search.retrieval",
                kind=SpanKind.DOMAIN,
                started_at_utc=now,
                duration_ms=retrieval_ms,
                request_id=ctx.request_id,
                operation="search",
            ),
        )
    if ranking_ms is not None:
        record_event(
            ObservabilityEvent(
                timestamp_utc=now,
                event_name=ObservabilityEventName.RANKING_COMPLETED,
                request_id=ctx.request_id,
                service_name=ctx.service_name,
                operation="search",
                outcome=ObservabilityOutcome.SUCCESS,
                duration_ms=ranking_ms,
                metadata=validate_event_metadata_safe(
                    {"result_count": result_count, "outcome": "success"},
                ),
            ),
        )
        record_span(
            ObservabilitySpan(
                span_name="search.ranking",
                kind=SpanKind.DOMAIN,
                started_at_utc=now,
                duration_ms=ranking_ms,
                request_id=ctx.request_id,
                operation="search",
            ),
        )


def emit_recommendation_request_completed(
    *,
    duration_ms: float,
    recommendation_type: str,
    result_count: int,
    top_k: int,
) -> None:
    ctx = build_observability_context(operation="recommendation")
    record_event(
        ObservabilityEvent(
            timestamp_utc=datetime.now(tz=UTC),
            event_name=ObservabilityEventName.RECOMMENDATION_REQUEST_COMPLETED,
            request_id=ctx.request_id,
            service_name=ctx.service_name,
            operation="recommendation",
            outcome=ObservabilityOutcome.SUCCESS,
            duration_ms=duration_ms,
            metadata=validate_event_metadata_safe(
                {
                    "recommendation_type": recommendation_type,
                    "result_count": result_count,
                    "top_k": top_k,
                    "outcome": "success",
                },
            ),
        ),
    )
    labels = {
        "operation": "recommendation",
        "outcome": "success",
        "recommendation_type": recommendation_type,
    }
    record_metric(
        MetricObservation(name=MetricName.RECOMMENDATION_REQUESTS_TOTAL, value=1.0, labels=labels),
    )
    record_metric(
        MetricObservation(
            name=MetricName.RECOMMENDATION_DURATION_MS,
            value=duration_ms,
            labels=labels,
        ),
    )


def emit_recommendation_generation_completed(*, duration_ms: float, candidate_count: int) -> None:
    ctx = build_observability_context(operation="recommendation")
    record_event(
        ObservabilityEvent(
            timestamp_utc=datetime.now(tz=UTC),
            event_name=ObservabilityEventName.RECOMMENDATION_GENERATION_COMPLETED,
            request_id=ctx.request_id,
            service_name=ctx.service_name,
            operation="recommendation",
            outcome=ObservabilityOutcome.SUCCESS,
            duration_ms=duration_ms,
            metadata=validate_event_metadata_safe(
                {"candidate_count": candidate_count, "outcome": "success"},
            ),
        ),
    )


def emit_product_request_completed(
    *,
    duration_ms: float,
    outcome: str,
    error_code: ApiErrorCode | None = None,
) -> None:
    ctx = build_observability_context(operation="product.get")
    obs_outcome = ObservabilityOutcome.SUCCESS if outcome == "success" else ObservabilityOutcome.FAILURE
    record_event(
        ObservabilityEvent(
            timestamp_utc=datetime.now(tz=UTC),
            event_name=ObservabilityEventName.PRODUCT_REQUEST_COMPLETED,
            request_id=ctx.request_id,
            service_name=ctx.service_name,
            operation="product.get",
            outcome=obs_outcome,
            duration_ms=duration_ms,
            error_code=error_code,
            metadata=validate_event_metadata_safe({"outcome": outcome}),
        ),
    )
    labels = {"operation": "get", "outcome": outcome}
    record_metric(
        MetricObservation(name=MetricName.PRODUCT_REQUESTS_TOTAL, value=1.0, labels=labels),
    )
    record_metric(
        MetricObservation(name=MetricName.PRODUCT_DURATION_MS, value=duration_ms, labels=labels),
    )
    if error_code is not None:
        record_metric(
            MetricObservation(
                name=MetricName.API_ERRORS_TOTAL,
                value=1.0,
                labels={"endpoint": "product", "operation": "get", "error_code": error_code.value},
            ),
        )


def measure_ms(start: float) -> float:
    return (time.perf_counter() - start) * 1000.0


__all__ = [
    "emit_product_request_completed",
    "emit_recommendation_generation_completed",
    "emit_recommendation_request_completed",
    "emit_search_request_completed",
    "emit_search_stage_from_timings",
    "measure_ms",
]
