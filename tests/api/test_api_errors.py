"""Cross-route error envelope and status code tests (Phase 13.7)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from productiq.api.app import create_app
from productiq.api.http_status import HTTP_STATUS_BY_API_ERROR
from productiq.api.middleware.request_id import REQUEST_ID_HEADER
from productiq.exceptions.base import CatalogLoadError, RecommendationError, RetrievalError
from productiq.serving.catalog_read import InMemoryProductCatalogReadProvider
from productiq.serving.errors import ApiErrorCode
from productiq.serving.product_service import ProductionProductServingService
from productiq.serving.versioning import (
    PLANNED_ROUTE_RECOMMENDATIONS,
    PLANNED_ROUTE_SEARCH,
    SERVING_API_ROUTE_PREFIX,
)
from tests.api.fakes import (
    RecordingProductService,
    RecordingRecommendationService,
    RecordingSearchService,
)


def _assert_error_envelope(response, *, code: ApiErrorCode, request_id: str | None = None) -> None:
    assert response.status_code == HTTP_STATUS_BY_API_ERROR[code]
    body = response.json()
    assert body["error"]["code"] == code.value
    assert body["error"]["message"]
    if request_id is not None:
        assert body["error"]["request_id"] == request_id
    assert "traceback" not in response.text.lower()


@pytest.mark.parametrize(
    ("factory", "call"),
    [
        (
            lambda: create_app(),
            lambda c: c.post(PLANNED_ROUTE_SEARCH, json={"query": "x", "top_k": 1}),
        ),
        (
            lambda: create_app(),
            lambda c: c.post(
                PLANNED_ROUTE_RECOMMENDATIONS,
                json={"seed_product_id": "P1", "top_k": 1},
            ),
        ),
        (
            lambda: create_app(),
            lambda c: c.get(f"{SERVING_API_ROUTE_PREFIX}/products/P1"),
        ),
    ],
)
def test_unconfigured_service_returns_configuration_error(factory, call) -> None:
    with TestClient(factory()) as client:
        response = call(client)
    _assert_error_envelope(response, code=ApiErrorCode.CONFIGURATION_ERROR)


def test_invalid_request_includes_request_id() -> None:
    app = create_app(search_service=RecordingSearchService())
    with TestClient(app) as client:
        response = client.post(
            PLANNED_ROUTE_SEARCH,
            json={"top_k": 1},
            headers={REQUEST_ID_HEADER: "err-req-1"},
        )
    _assert_error_envelope(response, code=ApiErrorCode.INVALID_REQUEST, request_id="err-req-1")


def test_not_found_product() -> None:
    app = create_app(
        product_service=ProductionProductServingService(InMemoryProductCatalogReadProvider({})),
    )
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get(f"{SERVING_API_ROUTE_PREFIX}/products/missing")
    _assert_error_envelope(response, code=ApiErrorCode.NOT_FOUND)


def test_internal_error_search() -> None:
    app = create_app(
        search_service=RecordingSearchService(error=RetrievalError("retrieval exploded")),
    )
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(PLANNED_ROUTE_SEARCH, json={"query": "shoes", "top_k": 1})
    _assert_error_envelope(response, code=ApiErrorCode.INTERNAL_ERROR)
    assert "traceback" not in response.text.lower()


def test_internal_error_recommendation() -> None:
    app = create_app(
        recommendation_service=RecordingRecommendationService(
            error=RecommendationError("ranking failed"),
        ),
    )
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            PLANNED_ROUTE_RECOMMENDATIONS,
            json={"seed_product_id": "P1", "top_k": 1},
        )
    _assert_error_envelope(response, code=ApiErrorCode.INTERNAL_ERROR)


def test_service_unavailable_product_catalog() -> None:
    app = create_app(
        product_service=RecordingProductService(error=CatalogLoadError("catalog down")),
    )
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get(f"{SERVING_API_ROUTE_PREFIX}/products/P1")
    _assert_error_envelope(response, code=ApiErrorCode.SERVICE_UNAVAILABLE)


@pytest.mark.parametrize("code", list(ApiErrorCode))
def test_every_api_error_code_has_http_mapping(code: ApiErrorCode) -> None:
    assert code in HTTP_STATUS_BY_API_ERROR
