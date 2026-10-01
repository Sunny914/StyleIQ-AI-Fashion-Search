"""Phase 13.6 integrated FastAPI application tests."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from productiq.api.app import create_app
from productiq.api.http_status import HTTP_STATUS_BY_API_ERROR
from productiq.api.middleware.request_id import REQUEST_ID_HEADER
from productiq.api.services.application_services import ApplicationServices
from productiq.api.services.application_wiring import build_application_services
from productiq.serving.catalog_read import InMemoryProductCatalogReadProvider
from productiq.serving.errors import ApiErrorCode
from productiq.serving.product_schema import ProductCatalogReadModel
from productiq.serving.product_service import ProductionProductServingService
from productiq.serving.recommendation_service import ProductionRecommendationServingService
from productiq.serving.search_service import ProductionSearchServingService
from productiq.serving.versioning import (
    PLANNED_ROUTE_HEALTH,
    PLANNED_ROUTE_READY,
    PLANNED_ROUTE_RECOMMENDATIONS,
    PLANNED_ROUTE_SEARCH,
    SERVING_API_ROUTE_PREFIX,
)
from tests.recommendation.test_recommendation_pipeline import _build_catalog, _build_pipeline
from tests.retrieval.test_production_ranking_integration import _ranked_pipeline


def _integrated_services() -> ApplicationServices:
    search_pipeline, _rrf, _cat = _ranked_pipeline(ranking=("P1", "P2"), pool_top_k=10)
    rec_catalog, filtering = _build_catalog("P1", "P2", "P3")
    rec_pipeline = _build_pipeline(rec_catalog, filtering)
    product_catalog = InMemoryProductCatalogReadProvider(
        {
            "P1": ProductCatalogReadModel(
                product_id="P1",
                brand="nike",
                description="Shirt",
                category_gender="Men",
                product_type="shirt",
            ),
        },
    )
    return build_application_services(
        search_service=ProductionSearchServingService(search_pipeline),
        recommendation_service=ProductionRecommendationServingService(rec_pipeline),
        product_service=ProductionProductServingService(product_catalog),
    )


def test_integrated_application_all_routes() -> None:
    services = _integrated_services()
    app = create_app(application_services=services)
    with TestClient(app) as client:
        health = client.get(PLANNED_ROUTE_HEALTH)
        ready = client.get(PLANNED_ROUTE_READY)
        search = client.post(PLANNED_ROUTE_SEARCH, json={"query": "shoes", "top_k": 1})
        rec = client.post(
            PLANNED_ROUTE_RECOMMENDATIONS,
            json={"seed_product_id": "P1", "top_k": 1},
        )
        product = client.get(f"{SERVING_API_ROUTE_PREFIX}/products/P1")
        openapi = client.get(f"{SERVING_API_ROUTE_PREFIX}/openapi.json")
    assert health.status_code == 200
    assert ready.json()["status"] == "ready"
    assert search.status_code == 200
    assert rec.status_code == 200
    assert product.status_code == 200
    paths = openapi.json()["paths"]
    assert PLANNED_ROUTE_SEARCH in paths
    assert PLANNED_ROUTE_RECOMMENDATIONS in paths
    assert "/api/v1/products/{product_id}" in paths


def test_service_instances_reused_across_requests() -> None:
    services = _integrated_services()
    app = create_app(application_services=services)
    search_id = id(app.state.search_service)
    product_id = id(app.state.product_service)
    with TestClient(app) as client:
        client.post(PLANNED_ROUTE_SEARCH, json={"query": "a", "top_k": 1})
        client.get(f"{SERVING_API_ROUTE_PREFIX}/products/P1")
        client.post(PLANNED_ROUTE_SEARCH, json={"query": "b", "top_k": 1})
    assert id(app.state.search_service) == search_id
    assert id(app.state.product_service) == product_id


def test_request_id_on_integrated_routes() -> None:
    app = create_app(application_services=_integrated_services())
    with TestClient(app) as client:
        response = client.post(
            PLANNED_ROUTE_SEARCH,
            json={"query": "shoes", "top_k": 1},
            headers={REQUEST_ID_HEADER: "integrated-req-1"},
        )
    assert response.json()["request_id"] == "integrated-req-1"
    assert response.headers[REQUEST_ID_HEADER] == "integrated-req-1"


def test_search_unconfigured_isolated_from_product() -> None:
    catalog = InMemoryProductCatalogReadProvider(
        {"P1": ProductCatalogReadModel(product_id="P1", brand="nike")},
    )
    services = build_application_services(
        product_service=ProductionProductServingService(catalog),
    )
    app = create_app(application_services=services)
    with TestClient(app) as client:
        search = client.post(PLANNED_ROUTE_SEARCH, json={"query": "x", "top_k": 1})
        product = client.get(f"{SERVING_API_ROUTE_PREFIX}/products/P1")
    assert search.status_code == HTTP_STATUS_BY_API_ERROR[ApiErrorCode.CONFIGURATION_ERROR]
    assert product.status_code == 200


def test_recommendation_unconfigured_isolated() -> None:
    services = _integrated_services()
    partial = ApplicationServices(
        serving_config=services.serving_config,
        search_service=services.search_service,
        product_service=services.product_service,
        recommendation_service=None,
    )
    app = create_app(application_services=partial)
    with TestClient(app) as client:
        search = client.post(PLANNED_ROUTE_SEARCH, json={"query": "shoes", "top_k": 1})
        rec = client.post(
            PLANNED_ROUTE_RECOMMENDATIONS,
            json={"seed_product_id": "P1", "top_k": 1},
        )
        product = client.get(f"{SERVING_API_ROUTE_PREFIX}/products/P1")
    assert search.status_code == 200
    assert rec.status_code == HTTP_STATUS_BY_API_ERROR[ApiErrorCode.CONFIGURATION_ERROR]
    assert product.status_code == 200


def test_product_unconfigured_isolated() -> None:
    services = _integrated_services()
    partial = ApplicationServices(
        serving_config=services.serving_config,
        search_service=services.search_service,
        recommendation_service=services.recommendation_service,
        product_service=None,
    )
    app = create_app(application_services=partial)
    with TestClient(app) as client:
        product = client.get(f"{SERVING_API_ROUTE_PREFIX}/products/P1")
        search = client.post(PLANNED_ROUTE_SEARCH, json={"query": "shoes", "top_k": 1})
    assert product.status_code == HTTP_STATUS_BY_API_ERROR[ApiErrorCode.CONFIGURATION_ERROR]
    assert search.status_code == 200


def test_integrated_responses_exclude_internal_fields() -> None:
    app = create_app(application_services=_integrated_services())
    with TestClient(app) as client:
        search = client.post(PLANNED_ROUTE_SEARCH, json={"query": "shoes", "top_k": 1})
        product = client.get(f"{SERVING_API_ROUTE_PREFIX}/products/P1")
    assert "bm25" not in json.dumps(search.json()).lower()
    assert "embedding" not in json.dumps(product.json()).lower()
