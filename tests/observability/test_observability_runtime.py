"""Runtime observability instrumentation tests (Phase 13.9-B)."""

from __future__ import annotations

import threading
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from productiq.api.app import create_app
from productiq.api.context import clear_request_id, set_request_id
from productiq.observability.events import ObservabilityEventName
from productiq.observability.metrics import MetricName
from productiq.observability.runtime.emitter import (
    bind_observability_sink,
    record_event,
    reset_observability_sink,
)
from productiq.observability.runtime.serving import emit_search_request_completed
from productiq.observability.runtime.sink import (
    InMemoryObservabilityCollector,
    NullObservabilitySink,
)
from productiq.recommendation.contracts import RecommendationRequest, RecommendationResponse
from productiq.recommendation.recommendation_pipeline_config import (
    RecommendationPipelineExecutionMetadata,
    RecommendationPipelineResult,
)
from productiq.retrieval.contracts import (
    RetrievalRequest,
    RetrievalResponseMetadata,
)
from productiq.retrieval.ranked_search import RankedSearchResponse, RankedSearchTimingsMs
from productiq.retrieval.ranking_integration import retrieval_order_ranking_response
from productiq.serving.catalog_read import InMemoryProductCatalogReadProvider
from productiq.serving.product_service import ProductionProductServingService, ProductNotFoundError
from productiq.serving.recommendation_schema import RecommendationApiRequest
from productiq.serving.recommendation_service import ProductionRecommendationServingService
from productiq.serving.search_schema import SearchApiRequest
from productiq.serving.search_service import ProductionSearchServingService
from tests.api.fakes import RecordingSearchService
from tests.serving.test_product_service import _sample_record


class _FakePipeline:
    def retrieve_ranked(self, request: RetrievalRequest) -> RankedSearchResponse:
        query = request.query
        empty = retrieval_order_ranking_response(
            query=query,
            filtered_candidates=(),
            top_k=request.top_k,
        )
        return RankedSearchResponse(
            ranking=empty,
            retrieval_metadata=RetrievalResponseMetadata(requested_top_k=request.top_k),
            ranking_pipeline_version="test",
            ranking_applied=False,
            candidate_count_after_filter=0,
            candidate_count_entering_ranking=0,
            timings_ms=RankedSearchTimingsMs(retrieval_ms=1.0, ranking_ms=2.0, total_ms=3.0),
        )


class _FakeRecommendationPipeline:
    def recommend_with_metadata(
        self,
        request: RecommendationRequest,
    ) -> RecommendationPipelineResult:
        response = RecommendationResponse(
            seed_product_id=request.seed_product_id,
            recommendation_type=request.recommendation_type,
            requested_top_k=request.top_k,
        )
        execution = RecommendationPipelineExecutionMetadata(
            candidate_count=3,
            ranked_count=0,
            selected_count=0,
        )
        return RecommendationPipelineResult(response=response, execution=execution)


def test_in_memory_collector_concurrent_emission() -> None:
    collector = InMemoryObservabilityCollector(max_entries_per_channel=200)

    def worker() -> None:
        token = bind_observability_sink(collector)
        emit_search_request_completed(
            duration_ms=1.0,
            result_count=1,
            top_k=1,
            query_length=3,
        )
        reset_observability_sink(token)

    threads = [threading.Thread(target=worker) for _ in range(20)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    events, metrics, _ = collector.snapshot()
    assert len(events) == 20
    assert len(metrics) >= 20


def test_telemetry_failure_does_not_break_caller() -> None:
    failing = MagicMock()
    failing.record_event.side_effect = RuntimeError("sink broken")
    token = bind_observability_sink(failing)
    try:
        emit_search_request_completed(
            duration_ms=1.0,
            result_count=0,
            top_k=5,
            query_length=4,
        )
    finally:
        reset_observability_sink(token)


def test_search_service_emits_domain_events() -> None:
    collector = InMemoryObservabilityCollector()
    token = bind_observability_sink(collector)
    set_request_id("search-req")
    try:
        service = ProductionSearchServingService(_FakePipeline())
        response = service.search(
            SearchApiRequest(query="shoes", top_k=5),
            request_id="search-req",
        )
        assert response.returned_count == 0
    finally:
        clear_request_id()
        reset_observability_sink(token)
    events, metrics, spans = collector.snapshot()
    assert any(e.event_name is ObservabilityEventName.SEARCH_REQUEST_COMPLETED for e in events)
    assert any(m.name is MetricName.SEARCH_REQUESTS_TOTAL for m in metrics)
    assert spans


def test_recommendation_service_emits_domain_events() -> None:
    collector = InMemoryObservabilityCollector()
    token = bind_observability_sink(collector)
    set_request_id("rec-req")
    try:
        service = ProductionRecommendationServingService(_FakeRecommendationPipeline())
        service.recommend(
            RecommendationApiRequest(seed_product_id="P1", top_k=2),
            request_id="rec-req",
        )
    finally:
        clear_request_id()
        reset_observability_sink(token)
    events, metrics, _ = collector.snapshot()
    assert any(
        e.event_name is ObservabilityEventName.RECOMMENDATION_REQUEST_COMPLETED for e in events
    )
    assert any(m.name is MetricName.RECOMMENDATION_REQUESTS_TOTAL for m in metrics)


def test_product_service_emits_found_and_not_found() -> None:
    catalog = InMemoryProductCatalogReadProvider({"p1": _sample_record("p1")})
    service = ProductionProductServingService(catalog)
    collector = InMemoryObservabilityCollector()
    token = bind_observability_sink(collector)
    set_request_id("prod-req")
    try:
        service.get_product("p1", request_id="prod-req")
        with pytest.raises(ProductNotFoundError):
            service.get_product("missing", request_id="prod-req")
    finally:
        clear_request_id()
        reset_observability_sink(token)
    events, _, _ = collector.snapshot()
    assert len([e for e in events if e.event_name.value.endswith("product.request.completed")]) >= 2


def test_api_middleware_emits_http_events() -> None:
    app = create_app(search_service=RecordingSearchService())
    collector = app.state.observability_sink
    assert isinstance(collector, InMemoryObservabilityCollector)
    client = TestClient(app)
    response = client.post(
        "/api/v1/search",
        json={"query": "shirt", "top_k": 5},
        headers={"X-Request-ID": "api-req-1"},
    )
    assert response.status_code == 200
    events, metrics, _ = collector.snapshot()
    names = {event.event_name for event in events}
    assert ObservabilityEventName.API_REQUEST_STARTED in names
    assert ObservabilityEventName.API_REQUEST_COMPLETED in names
    assert any(metric.name is MetricName.API_REQUESTS_TOTAL for metric in metrics)


def test_collector_capacity_drops_oldest() -> None:
    collector = InMemoryObservabilityCollector(max_entries_per_channel=2)
    token = bind_observability_sink(collector)
    try:
        for idx in range(4):
            record_event(
                __import__("productiq.observability.events", fromlist=["ObservabilityEvent"]).ObservabilityEvent(
                    timestamp_utc=datetime(2026, 1, 1, tzinfo=UTC),
                    event_name=ObservabilityEventName.API_REQUEST_STARTED,
                    service_name="productiq",
                    operation=f"op-{idx}",
                ),
            )
    finally:
        reset_observability_sink(token)
    events, _, _ = collector.snapshot()
    assert len(events) == 2
    assert collector.stats.dropped_events >= 2


def test_instrumentation_overhead_observation() -> None:
    service = RecordingSearchService()
    request = SearchApiRequest(query="hat", top_k=3)
    null_token = bind_observability_sink(NullObservabilitySink())
    try:
        start = datetime.now(tz=UTC)
        for _ in range(200):
            service.search(request, request_id="r")
        null_elapsed = (datetime.now(tz=UTC) - start).total_seconds()
    finally:
        reset_observability_sink(null_token)

    collector = InMemoryObservabilityCollector()
    mem_token = bind_observability_sink(collector)
    try:
        start = datetime.now(tz=UTC)
        for _ in range(200):
            service.search(request, request_id="r")
            emit_search_request_completed(
                duration_ms=0.1,
                result_count=1,
                top_k=3,
                query_length=3,
            )
        mem_elapsed = (datetime.now(tz=UTC) - start).total_seconds()
    finally:
        reset_observability_sink(mem_token)
    assert mem_elapsed < null_elapsed * 5.0 + 0.5
