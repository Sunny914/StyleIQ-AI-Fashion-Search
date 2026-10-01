"""Recommendation route behavioral coverage (Phase 13.7)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from productiq.api.app import create_app
from productiq.api.http_status import HTTP_STATUS_BY_API_ERROR
from productiq.recommendation.contracts import RecommendationType
from productiq.serving.errors import ApiErrorCode
from productiq.serving.recommendation_schema import (
    RecommendationApiResponse,
    RecommendationResultItem,
)
from productiq.serving.versioning import PLANNED_ROUTE_RECOMMENDATIONS
from tests.api.fakes import RecordingRecommendationService


def test_empty_recommendations_return_200() -> None:
    empty = RecommendationApiResponse(
        seed_product_id="P1",
        recommendation_type=RecommendationType.SIMILAR,
        top_k=5,
        recommendations=(),
        request_id="rid",
        returned_count=0,
    )
    app = create_app(recommendation_service=RecordingRecommendationService(response=empty))
    with TestClient(app) as client:
        response = client.post(
            PLANNED_ROUTE_RECOMMENDATIONS,
            json={"seed_product_id": "P1", "top_k": 5},
        )
    assert response.status_code == 200
    assert response.json()["returned_count"] == 0


def test_shortfall_below_top_k_returns_200() -> None:
    partial = RecommendationApiResponse(
        seed_product_id="P1",
        recommendation_type=RecommendationType.SIMILAR,
        top_k=5,
        recommendations=(
            RecommendationResultItem(product_id="P2", rank=1, recommendation_score=0.1),
        ),
        request_id="rid",
        returned_count=1,
    )
    app = create_app(recommendation_service=RecordingRecommendationService(response=partial))
    with TestClient(app) as client:
        response = client.post(
            PLANNED_ROUTE_RECOMMENDATIONS,
            json={"seed_product_id": "P1", "top_k": 5},
        )
    assert response.status_code == 200
    assert response.json()["returned_count"] == 1


def test_invalid_top_k_zero() -> None:
    app = create_app(recommendation_service=RecordingRecommendationService())
    with TestClient(app) as client:
        response = client.post(
            PLANNED_ROUTE_RECOMMENDATIONS,
            json={"seed_product_id": "P1", "top_k": 0},
        )
    assert response.status_code == HTTP_STATUS_BY_API_ERROR[ApiErrorCode.INVALID_REQUEST]
