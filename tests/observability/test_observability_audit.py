"""Phase 13.9-C observability hardening and final audit tests."""

from __future__ import annotations

import json
import threading
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from productiq.api.app import create_app
from productiq.api.context import clear_request_id, get_request_id, set_request_id
from productiq.exceptions.base import ValidationError as ProductIQValidationError
from productiq.observability.events import (
    PROHIBITED_METADATA_KEYS,
    ObservabilityEvent,
    ObservabilityEventName,
    validate_event_metadata,
)
from productiq.observability.metrics import MetricName, MetricObservation, validate_metric_labels
from productiq.observability.phase_13_9_audit import (
    EXPECTED_PRODUCT_SERVING_SPANS,
    EXPECTED_RECOMMENDATION_PIPELINE_SPANS,
    EXPECTED_SEARCH_SERVING_SPANS,
    audit_telemetry_snapshot,
)
from productiq.observability.runtime.emitter import (
    bind_observability_sink,
    emit_api_request_completed,
    record_event,
    record_metric,
    record_span,
    reset_observability_sink,
    validate_event_metadata_safe,
)
from productiq.observability.runtime.serving import emit_search_request_completed
from productiq.observability.runtime.sink import InMemoryObservabilityCollector
from productiq.observability.tracing import ObservabilitySpan, SpanKind
from productiq.observability.versioning import (
    OBSERVABILITY_CONTRACT_VERSION,
    OBSERVABILITY_RUNTIME_VERSION,
)
from productiq.recommendation.contracts import RecommendationRequest, RecommendationType
from productiq.serving.catalog_read import InMemoryProductCatalogReadProvider
from productiq.serving.product_service import ProductionProductServingService, ProductNotFoundError
from productiq.serving.recommendation_schema import RecommendationApiRequest
from productiq.serving.recommendation_service import ProductionRecommendationServingService
from productiq.serving.search_schema import SearchApiRequest
from productiq.serving.search_service import ProductionSearchServingService
from tests.api.fakes import RecordingSearchService
from tests.observability.test_observability_runtime import (
    _FakePipeline,
    _FakeRecommendationPipeline,
)
from tests.recommendation.test_recommendation_pipeline import _build_catalog, _build_pipeline
from tests.serving.test_product_service import _sample_record


def _failing_sink(*, fail_event: bool = False, fail_metric: bool = False, fail_span: bool = False) -> MagicMock:
    sink = MagicMock()
    if fail_event:
        sink.record_event.side_effect = RuntimeError("event sink failure")
    if fail_metric:
        sink.record_metric.side_effect = RuntimeError("metric sink failure")
    if fail_span:
        sink.record_span.side_effect = RuntimeError("span sink failure")
    return sink


@pytest.mark.parametrize(
    ("fail_event", "fail_metric", "fail_span"),
    [
        (True, False, False),
        (False, True, False),
        (False, False, True),
        (True, True, True),
    ],
)
def test_telemetry_sink_failures_do_not_break_search_service(
    fail_event: bool,
    fail_metric: bool,
    fail_span: bool,
) -> None:
    sink = _failing_sink(fail_event=fail_event, fail_metric=fail_metric, fail_span=fail_span)
    token = bind_observability_sink(sink)
    try:
        service = ProductionSearchServingService(_FakePipeline())
        response = service.search(SearchApiRequest(query="boots", top_k=3), request_id="iso-search")
        assert response.returned_count == 0
    finally:
        reset_observability_sink(token)


@pytest.mark.parametrize("fail_metric", [True, False])
def test_telemetry_failures_do_not_break_recommendation_service(fail_metric: bool) -> None:
    sink = _failing_sink(fail_event=True, fail_metric=fail_metric, fail_span=True)
    token = bind_observability_sink(sink)
    try:
        service = ProductionRecommendationServingService(_FakeRecommendationPipeline())
        response = service.recommend(
            RecommendationApiRequest(seed_product_id="P1", top_k=2),
            request_id="iso-rec",
        )
        assert response.seed_product_id == "P1"
    finally:
        reset_observability_sink(token)


def test_telemetry_failures_do_not_change_product_not_found() -> None:
    catalog = InMemoryProductCatalogReadProvider({})
    service = ProductionProductServingService(catalog)
    sink = _failing_sink(fail_event=True, fail_metric=True, fail_span=True)
    token = bind_observability_sink(sink)
    try:
        with pytest.raises(ProductNotFoundError):
            service.get_product("missing", request_id="iso-prod")
    finally:
        reset_observability_sink(token)


def test_record_event_swallows_collector_exceptions() -> None:
    sink = MagicMock()
    sink.record_event.side_effect = OSError("collector broken")
    token = bind_observability_sink(sink)
    try:
        record_event(
            ObservabilityEvent(
                timestamp_utc=datetime(2026, 1, 1, tzinfo=UTC),
                event_name=ObservabilityEventName.API_REQUEST_STARTED,
                service_name="productiq",
                operation="search",
            ),
        )
    finally:
        reset_observability_sink(token)


@pytest.mark.parametrize(
    "forbidden_key",
    ["password", "token", "authorization", "query", "embedding", "stack_trace"],
)
def test_runtime_metadata_validation_rejects_forbidden_keys(forbidden_key: str) -> None:
    with pytest.raises(ProductIQValidationError):
        validate_event_metadata_safe({forbidden_key: "leak"})


def test_runtime_api_emit_does_not_place_authorization_header_in_metadata() -> None:
    collector = InMemoryObservabilityCollector()
    token = bind_observability_sink(collector)
    set_request_id("hdr-req")
    try:
        emit_api_request_completed(
            operation="search",
            route="/api/v1/search",
            http_method="POST",
            status_code=200,
            duration_ms=1.0,
            result_count=1,
            top_k=5,
        )
    finally:
        clear_request_id()
        reset_observability_sink(token)
    events, metrics, spans = collector.snapshot()
    audit = audit_telemetry_snapshot(events, metrics, spans)
    assert audit["leakage_audit"]["passed"]
    assert audit["cardinality_audit"]["passed"]
    serialized = json.dumps([event.model_dump(mode="json") for event in events])
    assert "Bearer" not in serialized
    assert "Authorization" not in serialized


@pytest.mark.parametrize(
    "forbidden_label",
    ["request_id", "product_id", "seed_product_id", "query", "exception"],
)
def test_runtime_metric_emission_rejects_high_cardinality_labels(forbidden_label: str) -> None:
    with pytest.raises(ProductIQValidationError, match="high-cardinality"):
        validate_metric_labels(
            MetricName.SEARCH_REQUESTS_TOTAL,
            {"operation": "search", "outcome": "success", forbidden_label: "x"},
        )


def test_runtime_emitted_metrics_stay_on_allowlist() -> None:
    collector = InMemoryObservabilityCollector()
    token = bind_observability_sink(collector)
    set_request_id("metric-req")
    try:
        emit_search_request_completed(
            duration_ms=2.0,
            result_count=0,
            top_k=5,
            query_length=4,
        )
    finally:
        clear_request_id()
        reset_observability_sink(token)
    _, metrics, _ = collector.snapshot()
    findings = audit_telemetry_snapshot((), tuple(metrics), ())
    assert findings["cardinality_audit"]["passed"]


def test_search_serving_span_names_and_timing() -> None:
    collector = InMemoryObservabilityCollector()
    token = bind_observability_sink(collector)
    set_request_id("span-search")
    try:
        service = ProductionSearchServingService(_FakePipeline())
        service.search(SearchApiRequest(query="hat", top_k=2), request_id="span-search")
    finally:
        clear_request_id()
        reset_observability_sink(token)
    _, _, spans = collector.snapshot()
    names = {span.span_name for span in spans}
    assert EXPECTED_SEARCH_SERVING_SPANS.issubset(names)
    for span in spans:
        assert span.duration_ms is not None and span.duration_ms >= 0
        assert span.request_id == "span-search"
        assert span.operation == "search"


def test_recommendation_pipeline_span_names_and_timing() -> None:
    catalog, filtering = _build_catalog("P1", "P2", "P3")
    pipeline = _build_pipeline(catalog, filtering)
    collector = InMemoryObservabilityCollector()
    token = bind_observability_sink(collector)
    set_request_id("span-rec")
    try:
        pipeline.recommend_with_metadata(
            RecommendationRequest(
                seed_product_id="P1",
                recommendation_type=RecommendationType.SIMILAR,
                top_k=2,
            ),
        )
    finally:
        clear_request_id()
        reset_observability_sink(token)
    _, _, spans = collector.snapshot()
    names = {span.span_name for span in spans}
    assert EXPECTED_RECOMMENDATION_PIPELINE_SPANS.issubset(names)
    for span in spans:
        assert span.duration_ms is not None and span.duration_ms >= 0
        assert span.request_id == "span-rec"


def test_product_serving_span_names_and_timing() -> None:
    catalog = InMemoryProductCatalogReadProvider({"p1": _sample_record("p1")})
    service = ProductionProductServingService(catalog)
    collector = InMemoryObservabilityCollector()
    token = bind_observability_sink(collector)
    set_request_id("span-prod")
    try:
        service.get_product("p1", request_id="span-prod")
    finally:
        clear_request_id()
        reset_observability_sink(token)
    _, _, spans = collector.snapshot()
    names = {span.span_name for span in spans}
    assert EXPECTED_PRODUCT_SERVING_SPANS.issubset(names)
    for span in spans:
        assert span.duration_ms is not None and span.duration_ms >= 0


def test_http_request_id_propagates_to_observability_events() -> None:
    app = create_app(search_service=RecordingSearchService())
    collector = app.state.observability_sink
    client = TestClient(app)
    response = client.post(
        "/api/v1/search",
        json={"query": "coat", "top_k": 3},
        headers={
            "X-Request-ID": "correlation-http-42",
            "Authorization": "Bearer secret-token-should-not-leak",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("X-Request-ID") == "correlation-http-42"
    events, _, _ = collector.snapshot()
    assert events
    assert all(event.request_id == "correlation-http-42" for event in events if event.request_id)


def test_non_http_service_caller_uses_context_request_id() -> None:
    collector = InMemoryObservabilityCollector()
    token = bind_observability_sink(collector)
    set_request_id("service-only-id")
    try:
        assert get_request_id() == "service-only-id"
        emit_search_request_completed(
            duration_ms=1.0,
            result_count=0,
            top_k=1,
            query_length=3,
        )
    finally:
        clear_request_id()
        reset_observability_sink(token)
    events, _, _ = collector.snapshot()
    assert events[0].request_id == "service-only-id"


def test_observability_does_not_generate_second_request_id() -> None:
    set_request_id("primary-id")
    try:
        emit_search_request_completed(
            duration_ms=1.0,
            result_count=0,
            top_k=1,
            query_length=1,
        )
        assert get_request_id() == "primary-id"
    finally:
        clear_request_id()


def test_collector_concurrent_stress_maintains_capacity_and_counters() -> None:
    collector = InMemoryObservabilityCollector(max_entries_per_channel=50)
    barrier = threading.Barrier(10)

    def worker(worker_id: int) -> None:
        token = bind_observability_sink(collector)
        barrier.wait()
        for idx in range(30):
            record_event(
                ObservabilityEvent(
                    timestamp_utc=datetime(2026, 1, 1, tzinfo=UTC),
                    event_name=ObservabilityEventName.API_REQUEST_STARTED,
                    service_name="productiq",
                    operation=f"w{worker_id}-i{idx}",
                ),
            )
            record_metric(
                MetricObservation(
                    name=MetricName.API_REQUESTS_TOTAL,
                    value=1.0,
                    labels={
                        "endpoint": "search",
                        "operation": "search",
                        "status_class": "2xx",
                        "outcome": "success",
                    },
                ),
            )
            record_span(
                ObservabilitySpan(
                    span_name="search.query_representation",
                    kind=SpanKind.DOMAIN,
                    started_at_utc=datetime(2026, 1, 1, tzinfo=UTC),
                    duration_ms=float(idx),
                    operation="search",
                ),
            )
        reset_observability_sink(token)

    threads = [threading.Thread(target=worker, args=(worker_id,)) for worker_id in range(10)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    events, metrics, spans = collector.snapshot()
    assert len(events) == 50
    assert len(metrics) == 50
    assert len(spans) == 50
    assert collector.stats.dropped_events >= 250
    assert collector.stats.dropped_metrics >= 250
    assert collector.stats.dropped_spans >= 250


@pytest.mark.parametrize("channel", ["events", "metrics", "spans"])
def test_collector_capacity_drop_oldest_per_channel(channel: str) -> None:
    collector = InMemoryObservabilityCollector(max_entries_per_channel=3)
    if channel == "events":
        for idx in range(5):
            collector.record_event(
                ObservabilityEvent(
                    timestamp_utc=datetime(2026, 1, 1, tzinfo=UTC),
                    event_name=ObservabilityEventName.API_REQUEST_STARTED,
                    service_name="productiq",
                    operation=f"e{idx}",
                ),
            )
        events, metrics, spans = collector.snapshot()
        assert len(events) == 3
        assert collector.stats.dropped_events >= 2
        assert len(metrics) == 0
        assert len(spans) == 0
    elif channel == "metrics":
        for _ in range(5):
            collector.record_metric(
                MetricObservation(
                    name=MetricName.PRODUCT_REQUESTS_TOTAL,
                    value=1.0,
                    labels={"operation": "get", "outcome": "success"},
                ),
            )
        events, metrics, spans = collector.snapshot()
        assert len(metrics) == 3
        assert collector.stats.dropped_metrics >= 2
        assert len(events) == 0
    else:
        for idx in range(5):
            collector.record_span(
                ObservabilitySpan(
                    span_name="product.catalog_lookup",
                    kind=SpanKind.SERVING,
                    started_at_utc=datetime(2026, 1, 1, tzinfo=UTC),
                    duration_ms=float(idx),
                    operation="product.get",
                ),
            )
        _, metrics, spans = collector.snapshot()
        assert len(spans) == 3
        assert collector.stats.dropped_spans >= 2


def test_deterministic_contract_and_stage_names() -> None:
    assert OBSERVABILITY_CONTRACT_VERSION == "1.0.0"
    assert OBSERVABILITY_RUNTIME_VERSION == "1.0.0"
    assert ObservabilityEventName.SEARCH_REQUEST_COMPLETED.value == "search.request.completed"
    for key in PROHIBITED_METADATA_KEYS:
        with pytest.raises(ProductIQValidationError):
            validate_event_metadata({key: 1})


def test_application_composition_emits_search_recommendation_product_telemetry() -> None:
    catalog = InMemoryProductCatalogReadProvider({"p1": _sample_record("p1")})
    app = create_app(
        search_service=ProductionSearchServingService(_FakePipeline()),
        recommendation_service=ProductionRecommendationServingService(_FakeRecommendationPipeline()),
        product_service=ProductionProductServingService(catalog),
    )
    collector = app.state.observability_sink
    client = TestClient(app)
    search = client.post(
        "/api/v1/search",
        json={"query": "bag", "top_k": 2},
        headers={"X-Request-ID": "compose-1"},
    )
    rec = client.post(
        "/api/v1/recommendations",
        json={"seed_product_id": "p1", "top_k": 2},
        headers={"X-Request-ID": "compose-2"},
    )
    prod = client.get("/api/v1/products/p1", headers={"X-Request-ID": "compose-3"})
    assert search.status_code == 200
    assert rec.status_code == 200
    assert prod.status_code == 200
    events, metrics, spans = collector.snapshot()
    event_names = {event.event_name for event in events}
    assert ObservabilityEventName.SEARCH_REQUEST_COMPLETED in event_names
    assert ObservabilityEventName.RECOMMENDATION_REQUEST_COMPLETED in event_names
    assert ObservabilityEventName.PRODUCT_REQUEST_COMPLETED in event_names
    audit = audit_telemetry_snapshot(events, metrics, spans)
    assert audit["leakage_audit"]["passed"]
    assert audit["cardinality_audit"]["passed"]
    assert audit["stage_timing_audit"]["passed"]


def test_observability_runtime_imports_without_database() -> None:
    from productiq.observability.runtime import emitter, sink

    assert emitter is not None
    assert sink is not None


def test_instrumentation_overhead_repeated_observation_not_slo() -> None:
    """Repeat measurement to reduce noise; bound remains an observation only."""
    import time

    from productiq.observability.runtime.sink import NullObservabilitySink

    service = RecordingSearchService()
    request = SearchApiRequest(query="scarf", top_k=2)
    ratios: list[float] = []
    for _ in range(3):
        null_token = bind_observability_sink(NullObservabilitySink())
        start = time.perf_counter()
        for _ in range(100):
            service.search(request, request_id="r")
        null_elapsed = max(time.perf_counter() - start, 1e-6)
        reset_observability_sink(null_token)

        collector = InMemoryObservabilityCollector()
        mem_token = bind_observability_sink(collector)
        start = time.perf_counter()
        for _ in range(100):
            service.search(request, request_id="r")
            emit_search_request_completed(
                duration_ms=0.1,
                result_count=1,
                top_k=2,
                query_length=5,
            )
        mem_elapsed = time.perf_counter() - start
        reset_observability_sink(mem_token)
        ratios.append(mem_elapsed / null_elapsed)
    assert max(ratios) < 15.0
