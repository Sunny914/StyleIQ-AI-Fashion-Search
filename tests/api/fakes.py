"""Deterministic serving test doubles for HTTP/API tests (Phase 13.7)."""

from __future__ import annotations

from dataclasses import dataclass, field

from productiq.exceptions.base import RetrievalError
from productiq.serving.product_schema import ProductApiResponse
from productiq.serving.recommendation_schema import (
    RecommendationApiRequest,
    RecommendationApiResponse,
    RecommendationResultItem,
)
from productiq.serving.search_schema import SearchApiRequest, SearchApiResponse, SearchResultItem


@dataclass
class RecordingSearchService:
    calls: list[tuple[SearchApiRequest, str]] = field(default_factory=list)
    response: SearchApiResponse | None = None
    error: Exception | None = None

    def search(self, request: SearchApiRequest, *, request_id: str) -> SearchApiResponse:
        self.calls.append((request, request_id))
        if self.error is not None:
            raise self.error
        if self.response is not None:
            return self.response
        return SearchApiResponse(
            query=request.query,
            top_k=request.top_k,
            results=(SearchResultItem(product_id="P1", rank=1),),
            request_id=request_id,
            returned_count=1,
        )


@dataclass
class RecordingRecommendationService:
    calls: list[tuple[RecommendationApiRequest, str]] = field(default_factory=list)
    response: RecommendationApiResponse | None = None
    error: Exception | None = None

    def recommend(
        self,
        request: RecommendationApiRequest,
        *,
        request_id: str,
    ) -> RecommendationApiResponse:
        self.calls.append((request, request_id))
        if self.error is not None:
            raise self.error
        if self.response is not None:
            return self.response
        return RecommendationApiResponse(
            seed_product_id=request.seed_product_id,
            recommendation_type=request.recommendation_type,
            top_k=request.top_k,
            recommendations=(
                RecommendationResultItem(product_id="P2", rank=1, recommendation_score=0.5),
            ),
            request_id=request_id,
            returned_count=1,
        )


@dataclass
class RecordingProductService:
    calls: list[tuple[str, str]] = field(default_factory=list)
    response: ProductApiResponse | None = None
    error: Exception | None = None

    def get_product(self, product_id: str, *, request_id: str) -> ProductApiResponse:
        self.calls.append((product_id, request_id))
        if self.error is not None:
            raise self.error
        if self.response is not None:
            return self.response
        return ProductApiResponse(
            product_id=product_id,
            brand="puma",
            description="Shirt",
            image_url=None,
            product_url=None,
            category_gender="Men",
            product_type="shirt",
            request_id=request_id,
        )


def failing_search_service(message: str = "pipeline failed") -> RecordingSearchService:
    return RecordingSearchService(error=RetrievalError(message))


__all__ = [
    "RecordingProductService",
    "RecordingRecommendationService",
    "RecordingSearchService",
    "failing_search_service",
]
