"""Tests for Phase 13.1 API serving contracts."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from productiq.recommendation.contracts import RecommendationType
from productiq.serving import (
    PLANNED_ROUTE_HEALTH,
    PLANNED_ROUTE_RECOMMENDATIONS,
    PLANNED_ROUTE_SEARCH,
    SERVING_API_ROUTE_PREFIX,
    RecommendationApiRequest,
    SearchApiRequest,
)
from productiq.serving.health import HealthResponse, ReadinessResponse, ReadinessStatus
from productiq.serving.protocols import (
    HealthServingService,
    RecommendationServingService,
    SearchServingService,
)


class TestApiVersioning:
    def test_route_prefix(self) -> None:
        assert SERVING_API_ROUTE_PREFIX == "/api/v1"
        assert PLANNED_ROUTE_HEALTH == "/api/v1/health"
        assert PLANNED_ROUTE_SEARCH == "/api/v1/search"
        assert PLANNED_ROUTE_RECOMMENDATIONS == "/api/v1/recommendations"


class TestSearchApiRequest:
    def test_valid_minimal(self) -> None:
        body = SearchApiRequest(query="black Nike running shoes", top_k=10)
        assert body.query == "black Nike running shoes"
        assert body.filters is None

    def test_rejects_empty_query(self) -> None:
        with pytest.raises(ValidationError):
            SearchApiRequest(query="", top_k=10)

    def test_rejects_excessive_top_k(self) -> None:
        with pytest.raises(ValidationError):
            SearchApiRequest(query="shoes", top_k=101)


class TestRecommendationApiRequest:
    def test_similar_only(self) -> None:
        req = RecommendationApiRequest(seed_product_id="P1", top_k=5)
        assert req.recommendation_type is RecommendationType.SIMILAR

    def test_rejects_non_similar_type(self) -> None:
        with pytest.raises(ValidationError):
            RecommendationApiRequest(
                seed_product_id="P1",
                top_k=5,
                recommendation_type=RecommendationType.PERSONALIZED,
            )


class TestHealthContracts:
    def test_health_response(self) -> None:
        payload = HealthResponse(service="productiq", api_version="v1")
        assert payload.status == "ok"

    def test_readiness_response(self) -> None:
        payload = ReadinessResponse(status=ReadinessStatus.READY)
        assert payload.checks == ()


class TestServiceProtocols:
    def test_protocols_are_runtime_checkable(self) -> None:
        class FakeHealth:
            def health(self) -> HealthResponse:
                return HealthResponse(service="productiq", api_version="v1")

            def ready(self) -> ReadinessResponse:
                return ReadinessResponse(status=ReadinessStatus.READY)

        assert isinstance(FakeHealth(), HealthServingService)

        class FakeSearch:
            def search(self, request: SearchApiRequest, *, request_id: str) -> object:
                return request

        assert isinstance(FakeSearch(), SearchServingService)

        class FakeRec:
            def recommend(self, request: RecommendationApiRequest, *, request_id: str) -> object:
                return request

        assert isinstance(FakeRec(), RecommendationServingService)
