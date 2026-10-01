"""Opt-in recommendation API smoke through HTTP (Phase 13.4)."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from productiq.api.app import create_app
from productiq.serving.recommendation_service import ProductionRecommendationServingService
from productiq.serving.versioning import PLANNED_ROUTE_RECOMMENDATIONS
from tests.recommendation.test_recommendation_pipeline import _build_catalog, _build_pipeline

RECOMMENDATION_API_SMOKE_ENV_VAR = "PRODUCTIQ_RECOMMENDATION_API_SMOKE"
RECOMMENDATION_API_SMOKE_SKIP_REASON = (
    f"Set {RECOMMENDATION_API_SMOKE_ENV_VAR}=1 to run the optional recommendation API smoke."
)

pytestmark = pytest.mark.skipif(
    os.getenv(RECOMMENDATION_API_SMOKE_ENV_VAR) != "1",
    reason=RECOMMENDATION_API_SMOKE_SKIP_REASON,
)


def test_recommendation_api_smoke_http_path() -> None:
    """Full HTTP adapter → serving service → in-memory RecommendationPipeline (no PostgreSQL)."""
    catalog, filtering = _build_catalog("P1", "P2", "P3", "P4")
    pipeline = _build_pipeline(catalog, filtering)
    app = create_app(recommendation_service=ProductionRecommendationServingService(pipeline))
    with TestClient(app) as client:
        response = client.post(
            PLANNED_ROUTE_RECOMMENDATIONS,
            json={"seed_product_id": "P1", "top_k": 2, "recommendation_type": "similar"},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["seed_product_id"] == "P1"
    assert body["returned_count"] <= 2
