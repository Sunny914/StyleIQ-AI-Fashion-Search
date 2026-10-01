"""Tests for Phase 13.4 production recommendation serving service."""

from __future__ import annotations

import pytest

from productiq.exceptions.base import CatalogValidationError
from productiq.recommendation.contracts import RecommendationType
from productiq.recommendation.selection_config import RecommendationSelectionConfig
from productiq.representation.query_contract import QueryFilterConstraints
from productiq.serving.recommendation_schema import RecommendationApiRequest
from productiq.serving.recommendation_service import ProductionRecommendationServingService
from tests.recommendation.test_recommendation_pipeline import _build_catalog, _build_pipeline


def test_recommend_similar_returns_mapped_response() -> None:
    catalog, filtering = _build_catalog("P1", "P2", "P3")
    pipeline = _build_pipeline(catalog, filtering)
    service = ProductionRecommendationServingService(pipeline)
    response = service.recommend(
        RecommendationApiRequest(seed_product_id="P1", top_k=2),
        request_id="req-rec-1",
    )
    assert response.request_id == "req-rec-1"
    assert response.seed_product_id == "P1"
    assert response.recommendation_type is RecommendationType.SIMILAR
    assert response.top_k == 2
    assert response.returned_count <= 2


def test_recommend_propagates_seed_and_filters() -> None:
    catalog, filtering = _build_catalog("P1", "P2", "P3")
    pipeline = _build_pipeline(catalog, filtering)
    service = ProductionRecommendationServingService(pipeline)
    filters = QueryFilterConstraints(brand_normalized="nike")
    service.recommend(
        RecommendationApiRequest(
            seed_product_id="P1",
            top_k=3,
            filters=filters,
            recommendation_type=RecommendationType.SIMILAR,
        ),
        request_id="req-filters",
    )


def test_recommend_empty_results_success() -> None:
    catalog, filtering = _build_catalog("P1")
    pipeline = _build_pipeline(catalog, filtering)
    service = ProductionRecommendationServingService(pipeline)
    response = service.recommend(
        RecommendationApiRequest(seed_product_id="P1", top_k=5),
        request_id="req-empty",
    )
    assert response.returned_count == 0
    assert response.recommendations == ()


def test_recommend_shortfall() -> None:
    catalog, filtering = _build_catalog("P1", "P2", "P3", "P4")
    selection = RecommendationSelectionConfig(max_per_brand=1)
    pipeline = _build_pipeline(catalog, filtering, selection_config=selection)
    service = ProductionRecommendationServingService(pipeline)
    response = service.recommend(
        RecommendationApiRequest(seed_product_id="P1", top_k=4),
        request_id="req-shortfall",
    )
    assert response.returned_count < 4


def test_recommend_deterministic_ordering() -> None:
    catalog, filtering = _build_catalog("P1", "P2", "P3", "P4")
    pipeline = _build_pipeline(catalog, filtering)
    service = ProductionRecommendationServingService(pipeline)
    body = RecommendationApiRequest(seed_product_id="P1", top_k=3)
    first = service.recommend(body, request_id="a")
    second = service.recommend(body, request_id="b")
    assert first.recommendations == second.recommendations


def test_recommend_missing_seed_raises_catalog_validation() -> None:
    catalog, filtering = _build_catalog("P2")
    pipeline = _build_pipeline(catalog, filtering)
    service = ProductionRecommendationServingService(pipeline)
    with pytest.raises(CatalogValidationError, match="missing"):
        service.recommend(
            RecommendationApiRequest(seed_product_id="P1", top_k=1),
            request_id="req-missing",
        )


def test_recommend_response_excludes_internal_engine_fields() -> None:
    catalog, filtering = _build_catalog("P1", "P2", "P3")
    pipeline = _build_pipeline(catalog, filtering)
    service = ProductionRecommendationServingService(pipeline)
    response = service.recommend(
        RecommendationApiRequest(seed_product_id="P1", top_k=2),
        request_id="req-safe",
    )
    payload = response.model_dump(mode="json")
    dumped = str(payload).lower()
    assert "candidate_generation_score" not in dumped
    assert "vector_similarity" not in dumped
    assert "bm25" not in dumped
    assert "feature" not in dumped
    if response.recommendations:
        assert set(payload["recommendations"][0].keys()) == {
            "product_id",
            "rank",
            "recommendation_score",
        }
