"""Tests for Phase 13.5 GET /api/v1/products/{product_id}."""

from __future__ import annotations

import inspect

from fastapi.testclient import TestClient

from productiq.api.app import create_app
from productiq.api.dependencies import get_product_service
from productiq.api.http_status import HTTP_STATUS_BY_API_ERROR
from productiq.api.middleware.request_id import REQUEST_ID_HEADER
from productiq.api.routes import products as products_route
from productiq.exceptions.base import CatalogLoadError
from productiq.serving.catalog_read import InMemoryProductCatalogReadProvider
from productiq.serving.errors import ApiErrorCode
from productiq.serving.product_schema import ProductCatalogReadModel
from productiq.serving.product_service import ProductionProductServingService
from productiq.serving.versioning import SERVING_API_ROUTE_PREFIX
from tests.api.fakes import RecordingProductService


def _record(product_id: str = "123456789001") -> ProductCatalogReadModel:
    return ProductCatalogReadModel(
        product_id=product_id,
        brand="puma",
        description="Shirt",
        image_url="https://example.com/img",
        product_url="https://example.com/a",
        category_gender="Men",
        product_type="shirt",
    )


def test_product_route_requires_configured_service() -> None:
    app = create_app()
    with TestClient(app) as client:
        response = client.get(f"{SERVING_API_ROUTE_PREFIX}/products/P1")
    assert response.status_code == HTTP_STATUS_BY_API_ERROR[ApiErrorCode.CONFIGURATION_ERROR]


def test_product_route_success() -> None:
    catalog = InMemoryProductCatalogReadProvider({"P1": _record("P1")})
    app = create_app(product_service=ProductionProductServingService(catalog))
    with TestClient(app) as client:
        response = client.get(
            f"{SERVING_API_ROUTE_PREFIX}/products/P1",
            headers={REQUEST_ID_HEADER: "prod-req-7"},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["product_id"] == "P1"
    assert body["request_id"] == "prod-req-7"


def test_missing_product_returns_not_found() -> None:
    app = create_app(product_service=ProductionProductServingService(InMemoryProductCatalogReadProvider({})))
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get(f"{SERVING_API_ROUTE_PREFIX}/products/unknown")
    assert response.status_code == HTTP_STATUS_BY_API_ERROR[ApiErrorCode.NOT_FOUND]
    assert response.json()["error"]["message"] == "Product not found."


def test_dependency_override() -> None:
    recorder = RecordingProductService()
    app = create_app()
    app.dependency_overrides[get_product_service] = lambda: recorder
    with TestClient(app) as client:
        client.get(f"{SERVING_API_ROUTE_PREFIX}/products/X")
    assert recorder.calls == [("X", recorder.calls[0][1])]
    app.dependency_overrides.clear()


def test_catalog_load_error_maps_to_service_unavailable() -> None:
    failing = RecordingProductService(error=CatalogLoadError("catalog unavailable"))
    app = create_app(product_service=failing)
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get(f"{SERVING_API_ROUTE_PREFIX}/products/P1")
    assert response.status_code == HTTP_STATUS_BY_API_ERROR[ApiErrorCode.SERVICE_UNAVAILABLE]


def test_openapi_lists_product_endpoint() -> None:
    app = create_app(product_service=RecordingProductService())
    with TestClient(app) as client:
        paths = client.get(f"{SERVING_API_ROUTE_PREFIX}/openapi.json").json()["paths"]
    assert "/api/v1/products/{product_id}" in paths


def test_route_does_not_access_storage() -> None:
    source = inspect.getsource(products_route)
    assert "parquet" not in source.lower()
    assert "read_parquet" not in source
    assert "ProcessedParquet" not in source
