"""Application service protocols for HTTP serving (Phase 13.1).

FastAPI routes depend on these protocols; production wiring injects real pipelines,
tests inject fakes. No FastAPI imports here.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from productiq.serving.health import HealthResponse, ReadinessResponse
from productiq.serving.product_schema import ProductApiResponse
from productiq.serving.recommendation_schema import (
    RecommendationApiRequest,
    RecommendationApiResponse,
)
from productiq.serving.search_schema import SearchApiRequest, SearchApiResponse


@runtime_checkable
class HealthServingService(Protocol):
    def health(self) -> HealthResponse: ...

    def ready(self) -> ReadinessResponse: ...


@runtime_checkable
class SearchServingService(Protocol):
    """Orchestrates query understanding → production ranked search → API mapping."""

    def search(self, request: SearchApiRequest, *, request_id: str) -> SearchApiResponse: ...


@runtime_checkable
class RecommendationServingService(Protocol):
    """Orchestrates RecommendationPipeline → API mapping."""

    def recommend(
        self,
        request: RecommendationApiRequest,
        *,
        request_id: str,
    ) -> RecommendationApiResponse: ...


@runtime_checkable
class ProductServingService(Protocol):
    """Resolves catalog records through the product read boundary."""

    def get_product(self, product_id: str, *, request_id: str) -> ProductApiResponse: ...


__all__ = [
    "HealthServingService",
    "ProductServingService",
    "RecommendationServingService",
    "SearchServingService",
]
