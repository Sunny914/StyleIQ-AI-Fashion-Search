"""HTTP-level public API contract tests (Phase 13.7)."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from pydantic import TypeAdapter

from productiq.api.app import create_app
from productiq.serving.health import HealthResponse, ReadinessResponse
from productiq.serving.product_schema import ProductApiResponse
from productiq.serving.recommendation_schema import RecommendationApiResponse
from productiq.serving.search_schema import SearchApiResponse
from productiq.serving.versioning import (
    PLANNED_ROUTE_HEALTH,
    PLANNED_ROUTE_READY,
    PLANNED_ROUTE_RECOMMENDATIONS,
    PLANNED_ROUTE_SEARCH,
    SERVING_API_ROUTE_PREFIX,
)
from tests.api.fakes import (
    RecordingProductService,
    RecordingRecommendationService,
    RecordingSearchService,
)


def test_openapi_exposes_versioned_routes() -> None:
    app = create_app(
        search_service=RecordingSearchService(),
        recommendation_service=RecordingRecommendationService(),
        product_service=RecordingProductService(),
    )
    with TestClient(app) as client:
        spec = client.get(f"{SERVING_API_ROUTE_PREFIX}/openapi.json").json()
    paths = spec["paths"]
    for route in (
        PLANNED_ROUTE_HEALTH,
        PLANNED_ROUTE_READY,
        PLANNED_ROUTE_SEARCH,
        PLANNED_ROUTE_RECOMMENDATIONS,
        "/api/v1/products/{product_id}",
    ):
        assert route in paths


@pytest.mark.parametrize(
    ("route", "method", "payload"),
    [
        (PLANNED_ROUTE_SEARCH, "post", {"query": "shoes", "top_k": 2}),
        (
            PLANNED_ROUTE_RECOMMENDATIONS,
            "post",
            {"seed_product_id": "P1", "top_k": 2, "recommendation_type": "similar"},
        ),
    ],
)
def test_success_responses_match_pydantic_contracts(
    route: str,
    method: str,
    payload: dict[str, object],
) -> None:
    app = create_app(
        search_service=RecordingSearchService(),
        recommendation_service=RecordingRecommendationService(),
        product_service=RecordingProductService(),
    )
    with TestClient(app) as client:
        response = getattr(client, method)(route, json=payload)
    assert response.status_code == 200
    if route == PLANNED_ROUTE_SEARCH:
        TypeAdapter(SearchApiResponse).validate_python(response.json())
    else:
        TypeAdapter(RecommendationApiResponse).validate_python(response.json())


def test_health_and_ready_contracts() -> None:
    app = create_app()
    with TestClient(app) as client:
        health = client.get(PLANNED_ROUTE_HEALTH)
        ready = client.get(PLANNED_ROUTE_READY)
    TypeAdapter(HealthResponse).validate_python(health.json())
    TypeAdapter(ReadinessResponse).validate_python(ready.json())


def test_product_response_contract() -> None:
    app = create_app(product_service=RecordingProductService())
    with TestClient(app) as client:
        response = client.get(f"{SERVING_API_ROUTE_PREFIX}/products/P1")
    assert response.status_code == 200
    TypeAdapter(ProductApiResponse).validate_python(response.json())


def test_search_result_item_fields_only_public() -> None:
    app = create_app(search_service=RecordingSearchService())
    with TestClient(app) as client:
        response = client.post(PLANNED_ROUTE_SEARCH, json={"query": "shoes", "top_k": 1})
    item = response.json()["results"][0]
    assert set(item.keys()) == {"product_id", "rank"}


def test_recommendation_result_includes_public_score() -> None:
    app = create_app(recommendation_service=RecordingRecommendationService())
    with TestClient(app) as client:
        response = client.post(
            PLANNED_ROUTE_RECOMMENDATIONS,
            json={"seed_product_id": "P1", "top_k": 1},
        )
    item = response.json()["recommendations"][0]
    assert "recommendation_score" in item
    assert "product_id" in item
    assert "rank" in item


def test_error_envelope_shape_on_validation_failure() -> None:
    app = create_app(search_service=RecordingSearchService())
    with TestClient(app) as client:
        response = client.post(PLANNED_ROUTE_SEARCH, json={"query": "", "top_k": 1})
    body = response.json()
    assert set(body.keys()) == {"error"}
    assert set(body["error"].keys()) == {"code", "message", "request_id"}
    assert body["error"]["code"] == "INVALID_REQUEST"
    assert "traceback" not in json.dumps(body).lower()
