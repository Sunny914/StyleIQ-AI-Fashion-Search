"""Resilience telemetry via Phase 13.9 runtime (Phase 13.10-B)."""

from __future__ import annotations

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
    validate_event_metadata_safe,
)
from productiq.serving.errors import ApiErrorCode


def emit_traffic_rejection(
    *,
    operation: str,
    route: str,
    http_method: str,
    error_code: ApiErrorCode,
    status_code: int,
) -> None:
    ctx = build_observability_context(operation=operation)
    record_event(
        ObservabilityEvent(
            timestamp_utc=datetime.now(tz=UTC),
            event_name=ObservabilityEventName.API_REQUEST_COMPLETED,
            request_id=ctx.request_id,
            service_name=ctx.service_name,
            operation=operation,
            outcome=ObservabilityOutcome.FAILURE,
            error_code=error_code,
            metadata=validate_event_metadata_safe(
                {
                    "http_method": http_method,
                    "route": route,
                    "operation": operation,
                    "status_code": status_code,
                    "status_class": f"{status_code // 100}xx",
                    "outcome": "failure",
                    "layer": "resilience",
                },
            ),
        ),
    )
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


__all__ = ["emit_traffic_rejection"]
