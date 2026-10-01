"""Tests for Phase 13.1 domain → API mappers."""

from __future__ import annotations

from productiq.ranking.config import RankingConfig
from productiq.ranking.contracts import RankedCandidate, RankingCandidate, RankingResponse
from productiq.recommendation.config import RecommendationConfig
from productiq.recommendation.contracts import (
    RankedRecommendation,
    RecommendationCandidate,
    RecommendationCandidateSource,
    RecommendationResponse,
    RecommendationType,
)
from productiq.retrieval.contracts import (
    RetrievalCandidate,
    RetrievalMethod,
    RetrievalResponseMetadata,
)
from productiq.retrieval.ranked_search import RankedSearchResponse
from productiq.serving.mappers import (
    product_read_model_to_api,
    ranked_search_to_api_response,
    recommendation_response_to_api,
)
from productiq.serving.product_schema import ProductCatalogReadModel


def _retrieval_candidate(product_id: str) -> RetrievalCandidate:
    return RetrievalCandidate(
        product_id=product_id,
        score=0.5,
        method=RetrievalMethod.HYBRID,
        fusion_score=0.5,
    )


def test_ranked_search_mapper_strips_native_scores() -> None:
    rc = RankingCandidate(product_id="P1", retrieval=_retrieval_candidate("P1"))
    ranked = RankedSearchResponse(
        ranking=RankingResponse(
            ranked_candidates=(
                RankedCandidate(
                    product_id="P1",
                    rank=1,
                    ranking_score=0.9,
                    candidate=rc,
                ),
            ),
            requested_top_k=1,
            config=RankingConfig(),
        ),
        retrieval_metadata=RetrievalResponseMetadata(
            returned_candidate_count=1,
            requested_top_k=1,
        ),
        ranking_pipeline_version="test",
        ranking_applied=True,
        candidate_count_after_filter=1,
        candidate_count_entering_ranking=1,
    )
    api = ranked_search_to_api_response(
        ranked,
        query="shoes",
        top_k=10,
        request_id="req-search",
    )
    assert api.returned_count == 1
    assert api.results[0].product_id == "P1"
    assert api.results[0].rank == 1
    assert not hasattr(api.results[0], "bm25_score")


def test_recommendation_mapper() -> None:
    domain = RecommendationResponse(
        seed_product_id="S1",
        recommendation_type=RecommendationType.SIMILAR,
        recommendations=(
            RankedRecommendation(
                product_id="P2",
                rank=1,
                recommendation_score=0.77,
                candidate=RecommendationCandidate(
                    product_id="P2",
                    sources=(RecommendationCandidateSource.VECTOR,),
                    candidate_generation_score=0.5,
                ),
            ),
        ),
        requested_top_k=10,
        config=RecommendationConfig(),
    )
    api = recommendation_response_to_api(domain, request_id="req-rec")
    assert api.returned_count == 1
    assert api.recommendations[0].recommendation_score == 0.77
    assert api.recommendations[0].product_id == "P2"


def test_product_mapper() -> None:
    record = ProductCatalogReadModel(
        product_id="P99",
        brand="Example",
        description="A product",
        image_url="https://example/img.jpg",
    )
    api = product_read_model_to_api(record, request_id="req-prod")
    assert api.product_id == "P99"
    assert api.brand == "Example"
    assert api.request_id == "req-prod"
