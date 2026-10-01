"""Tests for Phase 13.4 POST /api/v1/recommendations."""

from __future__ import annotations

import inspect
import json

from fastapi.testclient import TestClient

from productiq.api.app import create_app
from productiq.api.dependencies import get_recommendation_service
from productiq.api.http_status import HTTP_STATUS_BY_API_ERROR
from productiq.api.middleware.request_id import REQUEST_ID_HEADER
from productiq.api.routes import recommendations as recommendations_route
from productiq.exceptions.base import RecommendationError
from productiq.serving.errors import ApiErrorCode
from productiq.serving.protocols import RecommendationServingService
from productiq.serving.recommendation_service import ProductionRecommendationServingService
from productiq.serving.versioning import PLANNED_ROUTE_RECOMMENDATIONS
from tests.api.fakes import RecordingRecommendationService
from tests.recommendation.test_recommendation_pipeline import _build_catalog, _build_pipeline


def test_recommendations_route_requires_configured_service() -> None:
    app = create_app()
    with TestClient(app) as client:
        response = client.post(
            PLANNED_ROUTE_RECOMMENDATIONS,
            json={"seed_product_id": "P1", "top_k": 3},
        )
    assert response.status_code == HTTP_STATUS_BY_API_ERROR[ApiErrorCode.CONFIGURATION_ERROR]


def test_recommendations_route_success() -> None:
    recorder = RecordingRecommendationService()
    app = create_app(recommendation_service=recorder)
    with TestClient(app) as client:
        response = client.post(
            PLANNED_ROUTE_RECOMMENDATIONS,
            json={"seed_product_id": "P1", "top_k": 3, "recommendation_type": "similar"},
            headers={REQUEST_ID_HEADER: "rec-req-1"},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["request_id"] == "rec-req-1"
    assert recorder.calls[0][0].seed_product_id == "P1"
    assert recorder.calls[0][0].top_k == 3
    assert recorder.calls[0][1] == "rec-req-1"


def test_recommendations_dependency_override() -> None:
    recorder = RecordingRecommendationService()
    app = create_app()
    app.dependency_overrides[get_recommendation_service] = lambda: recorder
    with TestClient(app) as client:
        response = client.post(
            PLANNED_ROUTE_RECOMMENDATIONS,
            json={"seed_product_id": "P1", "top_k": 1},
        )
    assert response.status_code == 200
    app.dependency_overrides.clear()


def test_unsupported_recommendation_type_invalid_request() -> None:
    app = create_app(recommendation_service=RecordingRecommendationService())
    with TestClient(app) as client:
        response = client.post(
            PLANNED_ROUTE_RECOMMENDATIONS,
            json={
                "seed_product_id": "P1",
                "top_k": 1,
                "recommendation_type": "personalized",
            },
        )
    assert response.status_code == HTTP_STATUS_BY_API_ERROR[ApiErrorCode.INVALID_REQUEST]


def test_top_k_above_maximum() -> None:
    app = create_app(recommendation_service=RecordingRecommendationService())
    with TestClient(app) as client:
        response = client.post(
            PLANNED_ROUTE_RECOMMENDATIONS,
            json={"seed_product_id": "P1", "top_k": 101},
        )
    assert response.status_code == HTTP_STATUS_BY_API_ERROR[ApiErrorCode.INVALID_REQUEST]


def test_missing_seed_product_not_found() -> None:
    catalog, filtering = _build_catalog("P2")
    pipeline = _build_pipeline(catalog, filtering)
    service: RecommendationServingService = ProductionRecommendationServingService(pipeline)
    app = create_app(recommendation_service=service)
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            PLANNED_ROUTE_RECOMMENDATIONS,
            json={"seed_product_id": "P1", "top_k": 3},
        )
    assert response.status_code == HTTP_STATUS_BY_API_ERROR[ApiErrorCode.NOT_FOUND]
    assert response.json()["error"]["message"] == "Seed product not found"
    assert "P1" not in response.text


def test_pipeline_failure_maps_to_internal_error() -> None:
    failing = RecordingRecommendationService(error=RecommendationError("ranking invariant failed"))
    app = create_app(recommendation_service=failing)
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            PLANNED_ROUTE_RECOMMENDATIONS,
            json={"seed_product_id": "P1", "top_k": 2},
        )
    assert response.status_code == HTTP_STATUS_BY_API_ERROR[ApiErrorCode.INTERNAL_ERROR]


def test_recommendations_with_in_memory_pipeline() -> None:
    catalog, filtering = _build_catalog("P1", "P2", "P3")
    pipeline = _build_pipeline(catalog, filtering)
    app = create_app(recommendation_service=ProductionRecommendationServingService(pipeline))
    with TestClient(app) as client:
        response = client.post(
            PLANNED_ROUTE_RECOMMENDATIONS,
            json={"seed_product_id": "P1", "top_k": 2},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["returned_count"] <= 2
    assert "candidate_generation" not in json.dumps(body).lower()


def test_openapi_lists_recommendations_endpoint() -> None:
    app = create_app(recommendation_service=RecordingRecommendationService())
    with TestClient(app) as client:
        paths = client.get("/api/v1/openapi.json").json()["paths"]
    assert "/api/v1/recommendations" in paths


def test_route_does_not_construct_pipeline() -> None:
    source = inspect.getsource(recommendations_route)
    assert "RecommendationPipeline" not in source
    assert "recommendation_wiring" not in source
