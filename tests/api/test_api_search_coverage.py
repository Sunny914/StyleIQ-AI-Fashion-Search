"""Search route behavioral coverage beyond Phase 13.3 (Phase 13.7)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from productiq.api.app import create_app
from productiq.api.http_status import HTTP_STATUS_BY_API_ERROR
from productiq.serving.errors import ApiErrorCode
from productiq.serving.search_schema import SearchApiResponse, SearchResultItem
from productiq.serving.versioning import PLANNED_ROUTE_SEARCH
from tests.api.fakes import RecordingSearchService


def test_top_k_zero_invalid_request() -> None:
    app = create_app(search_service=RecordingSearchService())
    with TestClient(app) as client:
        response = client.post(PLANNED_ROUTE_SEARCH, json={"query": "shoes", "top_k": 0})
    assert response.status_code == HTTP_STATUS_BY_API_ERROR[ApiErrorCode.INVALID_REQUEST]


def test_negative_top_k_invalid_request() -> None:
    app = create_app(search_service=RecordingSearchService())
    with TestClient(app) as client:
        response = client.post(PLANNED_ROUTE_SEARCH, json={"query": "shoes", "top_k": -1})
    assert response.status_code == HTTP_STATUS_BY_API_ERROR[ApiErrorCode.INVALID_REQUEST]


def test_top_k_at_default_maximum_succeeds() -> None:
    app = create_app(search_service=RecordingSearchService())
    with TestClient(app) as client:
        response = client.post(PLANNED_ROUTE_SEARCH, json={"query": "shoes", "top_k": 100})
    assert response.status_code == 200


def test_empty_results_return_200() -> None:
    empty = SearchApiResponse(
        query="none",
        top_k=5,
        results=(),
        request_id="rid",
        returned_count=0,
    )
    app = create_app(search_service=RecordingSearchService(response=empty))
    with TestClient(app) as client:
        response = client.post(PLANNED_ROUTE_SEARCH, json={"query": "none", "top_k": 5})
    assert response.status_code == 200
    assert response.json()["returned_count"] == 0


def test_rank_ordering_preserved() -> None:
    ordered = SearchApiResponse(
        query="shoes",
        top_k=2,
        results=(
            SearchResultItem(product_id="A", rank=1),
            SearchResultItem(product_id="B", rank=2),
        ),
        request_id="rid",
        returned_count=2,
    )
    app = create_app(search_service=RecordingSearchService(response=ordered))
    with TestClient(app) as client:
        response = client.post(PLANNED_ROUTE_SEARCH, json={"query": "shoes", "top_k": 2})
    ranks = [item["rank"] for item in response.json()["results"]]
    assert ranks == [1, 2]


def test_filters_forwarded_to_service() -> None:
    recorder = RecordingSearchService()
    app = create_app(search_service=recorder)
    with TestClient(app) as client:
        client.post(
            PLANNED_ROUTE_SEARCH,
            json={"query": "shoes", "top_k": 1, "filters": {"brand": "nike"}},
        )
    assert recorder.calls[0][0].filters is not None
