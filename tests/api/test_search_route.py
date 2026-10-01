"""Tests for Phase 13.3 POST /api/v1/search."""

from __future__ import annotations

import inspect
import json

from fastapi.testclient import TestClient

from productiq.api.app import create_app
from productiq.api.dependencies import get_search_service
from productiq.api.http_status import HTTP_STATUS_BY_API_ERROR
from productiq.api.middleware.request_id import REQUEST_ID_HEADER
from productiq.api.routes import search as search_route
from productiq.exceptions.base import RetrievalError
from productiq.serving.errors import ApiErrorCode
from productiq.serving.protocols import SearchServingService
from productiq.serving.search_service import ProductionSearchServingService
from productiq.serving.versioning import PLANNED_ROUTE_SEARCH
from tests.api.fakes import RecordingSearchService
from tests.retrieval.test_production_ranking_integration import _ranked_pipeline


def test_search_route_requires_configured_service() -> None:
    app = create_app()
    with TestClient(app) as client:
        response = client.post(PLANNED_ROUTE_SEARCH, json={"query": "shoes", "top_k": 5})
    assert response.status_code == HTTP_STATUS_BY_API_ERROR[ApiErrorCode.CONFIGURATION_ERROR]
    assert response.json()["error"]["code"] == "CONFIGURATION_ERROR"


def test_search_route_success_with_fake_service() -> None:
    recorder = RecordingSearchService()
    app = create_app(search_service=recorder)
    with TestClient(app) as client:
        response = client.post(
            PLANNED_ROUTE_SEARCH,
            json={"query": "nike shoes", "top_k": 3},
            headers={REQUEST_ID_HEADER: "client-req-99"},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["request_id"] == "client-req-99"
    assert body["returned_count"] == 1
    assert recorder.calls[0][0].query == "nike shoes"
    assert recorder.calls[0][0].top_k == 3
    assert recorder.calls[0][1] == "client-req-99"


def test_search_route_dependency_override() -> None:
    recorder = RecordingSearchService()
    app = create_app()
    app.dependency_overrides[get_search_service] = lambda: recorder
    with TestClient(app) as client:
        response = client.post(PLANNED_ROUTE_SEARCH, json={"query": "a", "top_k": 1})
    assert response.status_code == 200
    assert len(recorder.calls) == 1
    app.dependency_overrides.clear()


def test_search_invalid_body_returns_invalid_request() -> None:
    app = create_app(search_service=RecordingSearchService())
    with TestClient(app) as client:
        response = client.post(PLANNED_ROUTE_SEARCH, json={"query": "", "top_k": 1})
    assert response.status_code == HTTP_STATUS_BY_API_ERROR[ApiErrorCode.INVALID_REQUEST]


def test_search_top_k_above_maximum() -> None:
    app = create_app(search_service=RecordingSearchService())
    with TestClient(app) as client:
        response = client.post(PLANNED_ROUTE_SEARCH, json={"query": "shoes", "top_k": 101})
    assert response.status_code == HTTP_STATUS_BY_API_ERROR[ApiErrorCode.INVALID_REQUEST]


def test_search_domain_error_mapping() -> None:
    failing = RecordingSearchService(error=RetrievalError("pipeline failed"))
    app = create_app(search_service=failing)
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(PLANNED_ROUTE_SEARCH, json={"query": "shoes", "top_k": 2})
    assert response.status_code == HTTP_STATUS_BY_API_ERROR[ApiErrorCode.INTERNAL_ERROR]
    assert "traceback" not in response.text.lower()


def test_search_with_real_pipeline_via_service() -> None:
    pipeline, _rrf, _catalog = _ranked_pipeline(ranking=("P1", "P2"), pool_top_k=10)
    service: SearchServingService = ProductionSearchServingService(pipeline)
    app = create_app(search_service=service)
    with TestClient(app) as client:
        response = client.post(PLANNED_ROUTE_SEARCH, json={"query": "shoes", "top_k": 2})
    assert response.status_code == 200
    body = response.json()
    assert body["returned_count"] == 2
    assert "bm25" not in json.dumps(body).lower()


def test_search_openapi_lists_endpoint() -> None:
    app = create_app(search_service=RecordingSearchService())
    with TestClient(app) as client:
        openapi = client.get("/api/v1/openapi.json")
    paths = openapi.json()["paths"]
    assert "/api/v1/search" in paths
    assert "post" in paths["/api/v1/search"]


def test_route_does_not_import_production_factory() -> None:
    source = inspect.getsource(search_route)
    assert "production_factory" not in source
    assert "ProductionRetrievalPipeline" not in source
