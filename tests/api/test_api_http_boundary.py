"""HTTP boundary tests focused on ProductIQ contracts (Phase 13.7)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from productiq.api.app import create_app
from productiq.api.http_status import HTTP_STATUS_BY_API_ERROR
from productiq.serving.catalog_read import InMemoryProductCatalogReadProvider
from productiq.serving.errors import ApiErrorCode
from productiq.serving.product_service import ProductionProductServingService
from productiq.serving.versioning import (
    PLANNED_ROUTE_RECOMMENDATIONS,
    PLANNED_ROUTE_SEARCH,
    SERVING_API_ROUTE_PREFIX,
)
from tests.api.fakes import RecordingSearchService


def test_search_wrong_http_method() -> None:
    app = create_app(search_service=RecordingSearchService())
    with TestClient(app) as client:
        response = client.get(PLANNED_ROUTE_SEARCH)
    assert response.status_code == 405


def test_malformed_json_invalid_request() -> None:
    app = create_app(search_service=RecordingSearchService())
    with TestClient(app) as client:
        response = client.post(
            PLANNED_ROUTE_SEARCH,
            content=b"{not-json",
            headers={"Content-Type": "application/json"},
        )
    assert response.status_code == HTTP_STATUS_BY_API_ERROR[ApiErrorCode.INVALID_REQUEST]


def test_search_missing_required_field() -> None:
    app = create_app(search_service=RecordingSearchService())
    with TestClient(app) as client:
        response = client.post(PLANNED_ROUTE_SEARCH, json={"top_k": 3})
    assert response.status_code == HTTP_STATUS_BY_API_ERROR[ApiErrorCode.INVALID_REQUEST]


def test_recommendations_missing_seed_field() -> None:
    app = create_app()
    with TestClient(app) as client:
        response = client.post(PLANNED_ROUTE_RECOMMENDATIONS, json={"top_k": 1})
    assert response.status_code in {
        HTTP_STATUS_BY_API_ERROR[ApiErrorCode.INVALID_REQUEST],
        HTTP_STATUS_BY_API_ERROR[ApiErrorCode.CONFIGURATION_ERROR],
    }


def test_unknown_api_route_not_found() -> None:
    app = create_app()
    with TestClient(app) as client:
        response = client.get(f"{SERVING_API_ROUTE_PREFIX}/does-not-exist")
    assert response.status_code == 404


def test_product_get_with_valid_json_content_type_unnecessary() -> None:
    app = create_app(
        product_service=ProductionProductServingService(InMemoryProductCatalogReadProvider({})),
    )
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get(f"{SERVING_API_ROUTE_PREFIX}/products/P1")
    assert response.status_code == HTTP_STATUS_BY_API_ERROR[ApiErrorCode.NOT_FOUND]
