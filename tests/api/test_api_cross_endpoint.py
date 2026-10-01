"""Deterministic cross-endpoint integration tests (Phase 13.7)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from productiq.api.app import create_app
from productiq.api.services.application_wiring import build_application_services
from productiq.recommendation.contracts import RecommendationType
from productiq.serving.catalog_read import InMemoryProductCatalogReadProvider
from productiq.serving.product_schema import ProductCatalogReadModel
from productiq.serving.product_service import ProductionProductServingService
from productiq.serving.recommendation_schema import (
    RecommendationApiResponse,
    RecommendationResultItem,
)
from productiq.serving.search_schema import SearchApiResponse, SearchResultItem
from productiq.serving.versioning import (
    PLANNED_ROUTE_RECOMMENDATIONS,
    PLANNED_ROUTE_SEARCH,
    SERVING_API_ROUTE_PREFIX,
)
from tests.api.fakes import RecordingRecommendationService, RecordingSearchService
from tests.api.test_application_integration import _integrated_services


def test_search_then_product_identity_matches(integrated_client: TestClient) -> None:
    search = integrated_client.post(PLANNED_ROUTE_SEARCH, json={"query": "shoes", "top_k": 1})
    assert search.status_code == 200
    product_id = search.json()["results"][0]["product_id"]
    product = integrated_client.get(f"{SERVING_API_ROUTE_PREFIX}/products/{product_id}")
    assert product.status_code == 200
    assert product.json()["product_id"] == product_id


def test_product_then_recommendation_seed_flow(integrated_client: TestClient) -> None:
    product = integrated_client.get(f"{SERVING_API_ROUTE_PREFIX}/products/P1")
    assert product.status_code == 200
    rec = integrated_client.post(
        PLANNED_ROUTE_RECOMMENDATIONS,
        json={"seed_product_id": "P1", "top_k": 3},
    )
    assert rec.status_code == 200
    body = rec.json()
    ids = {item["product_id"] for item in body["recommendations"]}
    assert "P1" not in ids
    assert body["seed_product_id"] == "P1"


def test_coordinated_fakes_search_to_product_to_recommendation() -> None:
    search_fake = RecordingSearchService(
        response=SearchApiResponse(
            query="linked",
            top_k=1,
            results=(SearchResultItem(product_id="LINK-1", rank=1),),
            request_id="placeholder",
            returned_count=1,
        ),
    )
    catalog = InMemoryProductCatalogReadProvider(
        {
            "LINK-1": ProductCatalogReadModel(
                product_id="LINK-1",
                brand="nike",
                description="Linked product",
            ),
        },
    )
    rec_fake = RecordingRecommendationService(
        response=RecommendationApiResponse(
            seed_product_id="LINK-1",
            recommendation_type=RecommendationType.SIMILAR,
            top_k=1,
            recommendations=(
                RecommendationResultItem(product_id="LINK-2", rank=1, recommendation_score=0.9),
            ),
            request_id="placeholder",
            returned_count=1,
        ),
    )
    services = build_application_services(
        search_service=search_fake,
        recommendation_service=rec_fake,
        product_service=ProductionProductServingService(catalog),
    )
    app = create_app(application_services=services)
    with TestClient(app) as client:
        search = client.post(PLANNED_ROUTE_SEARCH, json={"query": "x", "top_k": 1})
        pid = search.json()["results"][0]["product_id"]
        product = client.get(f"{SERVING_API_ROUTE_PREFIX}/products/{pid}")
        rec = client.post(
            PLANNED_ROUTE_RECOMMENDATIONS,
            json={"seed_product_id": pid, "top_k": 1},
        )
    assert product.json()["product_id"] == "LINK-1"
    assert rec.json()["recommendations"][0]["product_id"] == "LINK-2"


def test_shared_serving_config_across_endpoints(integrated_client: TestClient) -> None:
    health = integrated_client.get("/api/v1/health")
    search = integrated_client.post(PLANNED_ROUTE_SEARCH, json={"query": "shoes", "top_k": 1})
    assert health.json()["api_version"] == "v1"
    assert search.status_code == 200


def test_integrated_services_fixture_matches_helper() -> None:
    assert _integrated_services().configured_service_names() == ("search", "recommendation", "product")
