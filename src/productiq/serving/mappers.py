"""Response mapping from domain pipelines to public API models (Phase 13.1)."""

from __future__ import annotations

from productiq.recommendation.contracts import RecommendationResponse
from productiq.retrieval.ranked_search import RankedSearchResponse
from productiq.serving.product_schema import ProductApiResponse, ProductCatalogReadModel
from productiq.serving.recommendation_schema import (
    RecommendationApiResponse,
    RecommendationResultItem,
)
from productiq.serving.search_schema import SearchApiResponse, SearchResultItem


def ranked_search_to_api_response(
    ranked: RankedSearchResponse,
    *,
    query: str,
    top_k: int,
    request_id: str,
) -> SearchApiResponse:
    """Project RankedSearchResponse into an API-safe search payload."""
    items: list[SearchResultItem] = []
    for row in ranked.ranking.ranked_candidates:
        items.append(
            SearchResultItem(
                product_id=row.candidate.retrieval.product_id,
                rank=row.rank,
            )
        )
    return SearchApiResponse(
        query=query,
        top_k=top_k,
        results=tuple(items),
        request_id=request_id,
        returned_count=len(items),
    )


def recommendation_response_to_api(
    response: RecommendationResponse,
    *,
    request_id: str,
) -> RecommendationApiResponse:
    """Project RecommendationResponse into an API-safe recommendation payload."""
    items = tuple(
        RecommendationResultItem(
            product_id=row.product_id,
            rank=row.rank,
            recommendation_score=row.recommendation_score,
        )
        for row in response.recommendations
    )
    return RecommendationApiResponse(
        seed_product_id=response.seed_product_id,
        recommendation_type=response.recommendation_type,
        top_k=response.requested_top_k,
        recommendations=items,
        request_id=request_id,
        returned_count=len(items),
    )


def product_read_model_to_api(
    record: ProductCatalogReadModel,
    *,
    request_id: str,
) -> ProductApiResponse:
    """Map catalog read model to the public product response."""
    return ProductApiResponse(
        product_id=record.product_id,
        brand=record.brand,
        description=record.description,
        image_url=record.image_url,
        product_url=record.product_url,
        category_gender=record.category_gender,
        product_type=record.product_type,
        request_id=request_id,
    )


__all__ = [
    "product_read_model_to_api",
    "ranked_search_to_api_response",
    "recommendation_response_to_api",
]
