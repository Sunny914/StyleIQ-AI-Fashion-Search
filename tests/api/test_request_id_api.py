"""Request-ID middleware behavior on API routes (Phase 13.7)."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from productiq.api.app import create_app
from productiq.api.middleware.request_id import MAX_REQUEST_ID_LENGTH, REQUEST_ID_HEADER
from productiq.serving.versioning import PLANNED_ROUTE_SEARCH
from tests.api.fakes import RecordingSearchService


def test_missing_header_generates_uuid_on_search() -> None:
    app = create_app(search_service=RecordingSearchService())
    with TestClient(app) as client:
        response = client.post(PLANNED_ROUTE_SEARCH, json={"query": "shoes", "top_k": 1})
    header = response.headers[REQUEST_ID_HEADER]
    body_id = response.json()["request_id"]
    assert header == body_id
    uuid.UUID(header)


def test_client_header_echoed_on_search() -> None:
    app = create_app(search_service=RecordingSearchService())
    supplied = "client-req-search-42"
    with TestClient(app) as client:
        response = client.post(
            PLANNED_ROUTE_SEARCH,
            json={"query": "shoes", "top_k": 1},
            headers={REQUEST_ID_HEADER: supplied},
        )
    assert response.headers[REQUEST_ID_HEADER] == supplied
    assert response.json()["request_id"] == supplied


def test_invalid_characters_replaced() -> None:
    app = create_app(search_service=RecordingSearchService())
    with TestClient(app) as client:
        response = client.post(
            PLANNED_ROUTE_SEARCH,
            json={"query": "shoes", "top_k": 1},
            headers={REQUEST_ID_HEADER: "bad id with spaces"},
        )
    generated = response.headers[REQUEST_ID_HEADER]
    assert generated != "bad id with spaces"
    uuid.UUID(generated)


def test_too_long_header_replaced() -> None:
    app = create_app(search_service=RecordingSearchService())
    too_long = "a" * (MAX_REQUEST_ID_LENGTH + 1)
    with TestClient(app) as client:
        response = client.post(
            PLANNED_ROUTE_SEARCH,
            json={"query": "shoes", "top_k": 1},
            headers={REQUEST_ID_HEADER: too_long},
        )
    generated = response.headers[REQUEST_ID_HEADER]
    assert generated != too_long
    uuid.UUID(generated)


def test_separate_requests_do_not_share_ids() -> None:
    app = create_app(search_service=RecordingSearchService())
    with TestClient(app) as client:
        first = client.post(PLANNED_ROUTE_SEARCH, json={"query": "a", "top_k": 1})
        second = client.post(PLANNED_ROUTE_SEARCH, json={"query": "b", "top_k": 1})
    assert first.json()["request_id"] != second.json()["request_id"]
