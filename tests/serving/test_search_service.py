"""Tests for Phase 13.3 production search serving service."""

from __future__ import annotations

import pytest

from productiq.representation.query_contract import QueryFilterConstraints
from productiq.retrieval.exceptions import RetrievalError
from productiq.serving.search_schema import SearchApiRequest
from productiq.serving.search_service import ProductionSearchServingService
from tests.retrieval.test_production_ranking_integration import _ranked_pipeline
from tests.retrieval.test_production_retrieval_pipeline import _pipeline


def test_search_returns_ranked_product_ids() -> None:
    pipeline, _rrf, _catalog = _ranked_pipeline(ranking=("P1", "P2", "P3"), pool_top_k=10)
    service = ProductionSearchServingService(pipeline)
    response = service.search(
        SearchApiRequest(query="nike shoes", top_k=2),
        request_id="req-search-1",
    )
    assert response.request_id == "req-search-1"
    assert response.query == "nike shoes"
    assert response.top_k == 2
    assert response.returned_count == 2
    assert [item.product_id for item in response.results] == ["P1", "P2"]
    assert [item.rank for item in response.results] == [1, 2]


def test_search_propagates_top_k_to_pipeline() -> None:
    pipeline, rrf, _catalog = _ranked_pipeline(ranking=tuple(f"P{i}" for i in range(1, 8)), pool_top_k=10)
    service = ProductionSearchServingService(pipeline)
    service.search(SearchApiRequest(query="shoes", top_k=3), request_id="req-topk")
    assert rrf.calls[0].top_k == 10
    assert rrf.calls[0].query.query_text == "shoes"


def test_search_applies_request_filters() -> None:
    ranking = ("P1", "P2", "P3")
    overrides = {
        "P1": {"brand_normalized": "nike"},
        "P2": {"brand_normalized": "adidas"},
        "P3": {"brand_normalized": "nike"},
    }
    pipeline, _rrf, catalog = _ranked_pipeline(
        ranking=ranking,
        pool_top_k=10,
        product_overrides=overrides,
    )
    service = ProductionSearchServingService(pipeline)
    response = service.search(
        SearchApiRequest(
            query="shoes",
            top_k=5,
            filters=QueryFilterConstraints(brand_normalized="nike"),
        ),
        request_id="req-filter",
    )
    assert catalog.calls
    assert response.returned_count >= 1
    assert all(item.product_id in {"P1", "P3"} for item in response.results)


def test_search_empty_results_not_an_error() -> None:
    ranking = ("P1",)
    overrides = {"P1": {"brand_normalized": "nike"}}
    pipeline, _rrf, _catalog = _ranked_pipeline(
        ranking=ranking,
        pool_top_k=10,
        product_overrides=overrides,
    )
    service = ProductionSearchServingService(pipeline)
    response = service.search(
        SearchApiRequest(
            query="shoes",
            top_k=5,
            filters=QueryFilterConstraints(brand_normalized="brand_that_does_not_exist"),
        ),
        request_id="req-empty",
    )
    assert response.returned_count == 0
    assert response.results == ()


def test_search_deterministic_ordering() -> None:
    pipeline, _rrf, _catalog = _ranked_pipeline(ranking=("P1", "P2", "P3"), pool_top_k=10)
    service = ProductionSearchServingService(pipeline)
    request = SearchApiRequest(query="shoes", top_k=3)
    first = service.search(request, request_id="a")
    second = service.search(request, request_id="b")
    assert first.results == second.results


def test_search_response_has_no_internal_scores() -> None:
    pipeline, _rrf, _catalog = _ranked_pipeline(ranking=("P1", "P2"), pool_top_k=10)
    service = ProductionSearchServingService(pipeline)
    response = service.search(SearchApiRequest(query="x", top_k=2), request_id="req-safe")
    payload = response.model_dump(mode="json")
    dumped = str(payload).lower()
    assert "bm25" not in dumped
    assert "vector" not in dumped
    assert "rrf" not in dumped
    assert "score" not in dumped
    assert set(payload["results"][0].keys()) == {"product_id", "rank"}


def test_search_normalizes_query_text() -> None:
    pipeline, _rrf, _catalog = _ranked_pipeline(ranking=("P1",), pool_top_k=5)
    service = ProductionSearchServingService(pipeline)
    response = service.search(
        SearchApiRequest(query="  navy   shirt  ", top_k=1),
        request_id="req-norm",
    )
    assert response.query == "navy shirt"


def test_search_domain_error_propagates() -> None:
    pipeline, rrf, _catalog = _pipeline(ranking=("P1",), pool_top_k=5)
    rrf.fail_with = RetrievalError("contract violation")
    service = ProductionSearchServingService(pipeline)
    with pytest.raises(RetrievalError):
        service.search(SearchApiRequest(query="x", top_k=1), request_id="req-err")
