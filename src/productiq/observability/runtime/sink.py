"""In-memory observability sink (Phase 13.9-B)."""

from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass
from typing import Any, Protocol

from productiq.observability.events import ObservabilityEvent
from productiq.observability.metrics import MetricObservation
from productiq.observability.tracing import ObservabilitySpan


class ObservabilitySink(Protocol):
    """Vendor-neutral telemetry sink."""

    def record_event(self, event: ObservabilityEvent) -> None: ...

    def record_metric(self, observation: MetricObservation) -> None: ...

    def record_span(self, span: ObservabilitySpan) -> None: ...


@dataclass
class ObservabilityCollectorStats:
    events_recorded: int = 0
    metrics_recorded: int = 0
    spans_recorded: int = 0
    dropped_events: int = 0
    dropped_metrics: int = 0
    dropped_spans: int = 0


class NullObservabilitySink:
    """No-op sink for disabled telemetry or baseline overhead measurement."""

    def record_event(self, event: ObservabilityEvent) -> None:
        _ = event

    def record_metric(self, observation: MetricObservation) -> None:
        _ = observation

    def record_span(self, span: ObservabilitySpan) -> None:
        _ = span


class InMemoryObservabilityCollector:
    """Thread-safe bounded in-memory collector for tests and local development."""

    def __init__(self, *, max_entries_per_channel: int = 5000) -> None:
        if max_entries_per_channel < 1:
            msg = "max_entries_per_channel must be >= 1"
            raise ValueError(msg)
        self._max = max_entries_per_channel
        self._lock = threading.Lock()
        self._events: deque[ObservabilityEvent] = deque()
        self._metrics: deque[MetricObservation] = deque()
        self._spans: deque[ObservabilitySpan] = deque()
        self.stats = ObservabilityCollectorStats()

    def _append(self, channel: deque[Any], item: object, *, dropped_attr: str) -> None:
        if len(channel) >= self._max:
            channel.popleft()
            current = getattr(self.stats, dropped_attr)
            setattr(self.stats, dropped_attr, current + 1)
        channel.append(item)

    def record_event(self, event: ObservabilityEvent) -> None:
        with self._lock:
            self._append(self._events, event, dropped_attr="dropped_events")
            self.stats.events_recorded += 1

    def record_metric(self, observation: MetricObservation) -> None:
        with self._lock:
            self._append(self._metrics, observation, dropped_attr="dropped_metrics")
            self.stats.metrics_recorded += 1

    def record_span(self, span: ObservabilitySpan) -> None:
        with self._lock:
            self._append(self._spans, span, dropped_attr="dropped_spans")
            self.stats.spans_recorded += 1

    def snapshot(self) -> tuple[tuple[ObservabilityEvent, ...], tuple[MetricObservation, ...], tuple[ObservabilitySpan, ...]]:
        with self._lock:
            return (tuple(self._events), tuple(self._metrics), tuple(self._spans))

    def clear(self) -> None:
        with self._lock:
            self._events.clear()
            self._metrics.clear()
            self._spans.clear()


__all__ = [
    "InMemoryObservabilityCollector",
    "NullObservabilitySink",
    "ObservabilityCollectorStats",
    "ObservabilitySink",
]
