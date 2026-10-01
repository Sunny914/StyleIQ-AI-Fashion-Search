"""ProductIQ observability contracts (Phase 13.9.1)."""

from __future__ import annotations

from productiq.observability.context import (
    DEFAULT_SERVICE_NAME,
    ObservabilityContext,
    build_observability_context,
)
from productiq.observability.events import (
    ObservabilityEvent,
    ObservabilityEventName,
    ObservabilityOutcome,
    assert_registered_event_name,
    validate_event_metadata,
)
from productiq.observability.metrics import (
    MetricName,
    MetricObservation,
    validate_metric_labels,
)
from productiq.observability.tracing import ObservabilitySpan, SpanKind
from productiq.observability.versioning import OBSERVABILITY_CONTRACT_VERSION

__all__ = [
    "DEFAULT_SERVICE_NAME",
    "OBSERVABILITY_CONTRACT_VERSION",
    "MetricName",
    "MetricObservation",
    "ObservabilityContext",
    "ObservabilityEvent",
    "ObservabilityEventName",
    "ObservabilityOutcome",
    "ObservabilitySpan",
    "SpanKind",
    "assert_registered_event_name",
    "build_observability_context",
    "validate_event_metadata",
    "validate_metric_labels",
]
