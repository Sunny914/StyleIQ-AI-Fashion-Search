"""Centralized telemetry emission (Phase 13.9-B)."""

from __future__ import annotations

import contextvars
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime

from productiq.observability.context import build_observability_context
from productiq.observability.events import (
    ObservabilityEvent,
    ObservabilityEventName,
    ObservabilityOutcome,
    validate_event_metadata,
)
from productiq.observability.metrics import MetricName, MetricObservation
from productiq.observability.runtime.sink import NullObservabilitySink, ObservabilitySink
from productiq.observability.tracing import ObservabilitySpan, SpanKind
from productiq.serving.errors import ApiErrorCode

_sink_var: contextvars.ContextVar[ObservabilitySink | None] = contextvars.ContextVar(
    "productiq_observability_sink",
    default=None,
)

_default_sink: ObservabilitySink = NullObservabilitySink()


def set_default_observability_sink(sink: ObservabilitySink) -> None:
    global _default_sink
    _default_sink = sink


def bind_observability_sink(sink: ObservabilitySink | None) -> contextvars.Token[ObservabilitySink | None]:
    return _sink_var.set(sink)


def reset_observability_sink(token: contextvars.Token[ObservabilitySink | None]) -> None:
    _sink_var.reset(token)


def get_observability_sink() -> ObservabilitySink:
    bound = _sink_var.get()
    if bound is not None:
        return bound
    return _default_sink


def _safe_emit(action: Callable[[], None]) -> None:
    try:
        action()
    except Exception:  # noqa: BLE001 - telemetry must not affect request handling
        return


def record_event(event: ObservabilityEvent) -> None:
    def _emit() -> None:
        get_observability_sink().record_event(event)

    _safe_emit(_emit)


def record_metric(observation: MetricObservation) -> None:
    def _emit() -> None:
        get_observability_sink().record_metric(observation)

    _safe_emit(_emit)


def record_span(span: ObservabilitySpan) -> None:
    def _emit() -> None:
        get_observability_sink().record_span(span)

    _safe_emit(_emit)


def http_status_class(status_code: int) -> str:
    return f"{status_code // 100}xx"


def api_error_code_from_http_status(status_code: int) -> ApiErrorCode:
    if status_code == 429:
        return ApiErrorCode.RATE_LIMITED
    if status_code == 404:
        return ApiErrorCode.NOT_FOUND
    if status_code == 400:
        return ApiErrorCode.INVALID_REQUEST
    if status_code == 503:
        return ApiErrorCode.SERVICE_UNAVAILABLE
    if status_code >= 500:
        return ApiErrorCode.INTERNAL_ERROR
    return ApiErrorCode.INVALID_REQUEST


def emit_api_request_started(*, operation: str, route: str, http_method: str) -> None:
    ctx = build_observability_context(operation=operation)
    metadata = validate_event_metadata_safe(
        {"http_method": http_method, "route": route, "operation": operation},
    )
    record_event(
        ObservabilityEvent(
            timestamp_utc=datetime.now(tz=UTC),
            event_name=ObservabilityEventName.API_REQUEST_STARTED,
            request_id=ctx.request_id,
            service_name=ctx.service_name,
            operation=operation,
            metadata=metadata,
        ),
    )


def emit_api_request_completed(
    *,
    operation: str,
    route: str,
    http_method: str,
    status_code: int,
    duration_ms: float,
    result_count: int | None = None,
    top_k: int | None = None,
) -> None:
    ctx = build_observability_context(operation=operation)
    metadata_payload: dict[str, str | int | float | bool] = {
        "http_method": http_method,
        "route": route,
        "operation": operation,
        "status_code": status_code,
        "status_class": http_status_class(status_code),
        "outcome": "success" if status_code < 400 else "failure",
    }
    if result_count is not None:
        metadata_payload["result_count"] = result_count
    if top_k is not None:
        metadata_payload["top_k"] = top_k
    metadata = validate_event_metadata_safe(metadata_payload)
    outcome = ObservabilityOutcome.SUCCESS if status_code < 400 else ObservabilityOutcome.FAILURE
    error_code = None if status_code < 400 else api_error_code_from_http_status(status_code)
    record_event(
        ObservabilityEvent(
            timestamp_utc=datetime.now(tz=UTC),
            event_name=ObservabilityEventName.API_REQUEST_COMPLETED,
            request_id=ctx.request_id,
            service_name=ctx.service_name,
            operation=operation,
            outcome=outcome,
            duration_ms=duration_ms,
            error_code=error_code,
            metadata=metadata,
        ),
    )
    labels = {
        "endpoint": operation,
        "operation": operation,
        "status_class": http_status_class(status_code),
        "outcome": "success" if status_code < 400 else "failure",
    }
    record_metric(
        MetricObservation(name=MetricName.API_REQUESTS_TOTAL, value=1.0, labels=labels),
    )
    record_metric(
        MetricObservation(
            name=MetricName.API_REQUEST_DURATION_MS,
            value=duration_ms,
            labels={
                "endpoint": operation,
                "operation": operation,
                "status_class": http_status_class(status_code),
            },
        ),
    )
    if status_code >= 400 and error_code is not None:
        record_metric(
            MetricObservation(
                name=MetricName.API_ERRORS_TOTAL,
                value=1.0,
                labels={
                    "endpoint": operation,
                    "operation": operation,
                    "error_code": error_code.value,
                },
            ),
        )


def emit_api_request_failed(
    *,
    operation: str,
    route: str,
    http_method: str,
    duration_ms: float,
    error_code: ApiErrorCode,
) -> None:
    ctx = build_observability_context(operation=operation)
    metadata = validate_event_metadata_safe(
        {
            "http_method": http_method,
            "route": route,
            "operation": operation,
            "outcome": "failure",
        },
    )
    record_event(
        ObservabilityEvent(
            timestamp_utc=datetime.now(tz=UTC),
            event_name=ObservabilityEventName.API_REQUEST_FAILED,
            request_id=ctx.request_id,
            service_name=ctx.service_name,
            operation=operation,
            outcome=ObservabilityOutcome.FAILURE,
            duration_ms=duration_ms,
            error_code=error_code,
            metadata=metadata,
        ),
    )


def validate_event_metadata_safe(
    metadata: dict[str, str | int | float | bool],
) -> dict[str, str | int | float | bool]:
    validate_event_metadata(metadata)
    return metadata


@contextmanager
def observe_stage(
    span_name: str,
    *,
    kind: SpanKind,
    operation: str,
) -> Iterator[None]:
    start = time.perf_counter()
    started_at = datetime.now(tz=UTC)
    try:
        yield
    finally:
        duration_ms = (time.perf_counter() - start) * 1000.0
        ctx = build_observability_context(operation=operation)
        record_span(
            ObservabilitySpan(
                span_name=span_name,
                kind=kind,
                started_at_utc=started_at,
                duration_ms=duration_ms,
                request_id=ctx.request_id,
                operation=operation,
            ),
        )


__all__ = [
    "api_error_code_from_http_status",
    "bind_observability_sink",
    "emit_api_request_completed",
    "emit_api_request_failed",
    "emit_api_request_started",
    "get_observability_sink",
    "http_status_class",
    "observe_stage",
    "record_event",
    "record_metric",
    "record_span",
    "reset_observability_sink",
    "set_default_observability_sink",
    "validate_event_metadata_safe",
]
