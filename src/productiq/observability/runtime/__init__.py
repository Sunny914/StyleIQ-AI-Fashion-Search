"""Runtime observability wiring (Phase 13.9-B)."""

from __future__ import annotations

from productiq.observability.runtime.emitter import (
    bind_observability_sink,
    get_observability_sink,
    record_event,
    record_metric,
    record_span,
    reset_observability_sink,
    set_default_observability_sink,
)
from productiq.observability.runtime.serving import (
    emit_product_request_completed,
    emit_recommendation_request_completed,
    emit_search_request_completed,
)
from productiq.observability.runtime.sink import (
    InMemoryObservabilityCollector,
    NullObservabilitySink,
    ObservabilitySink,
)

__all__ = [
    "InMemoryObservabilityCollector",
    "NullObservabilitySink",
    "ObservabilitySink",
    "bind_observability_sink",
    "emit_product_request_completed",
    "emit_recommendation_request_completed",
    "emit_search_request_completed",
    "get_observability_sink",
    "record_event",
    "record_metric",
    "record_span",
    "reset_observability_sink",
    "set_default_observability_sink",
]
