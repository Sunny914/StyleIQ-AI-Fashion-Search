"""Public recommendation API contracts (Phase 13.1).

Maps to RecommendationPipeline and RecommendationRequest in Phase 13.2.
Production API surface supports SIMILAR only.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from productiq.recommendation.contracts import RecommendationType
from productiq.representation.query_contract import QueryFilterConstraints
from productiq.serving.search_schema import resolve_api_max_top_k


class RecommendationApiRequest(BaseModel):
    """POST /api/v1/recommendations body."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    seed_product_id: str = Field(min_length=1)
    recommendation_type: RecommendationType = Field(
        default=RecommendationType.SIMILAR,
        description="Production API currently implements SIMILAR only.",
    )
    top_k: int = Field(gt=0)
    filters: QueryFilterConstraints | None = None

    @model_validator(mode="after")
    def validate_production_scope(self) -> RecommendationApiRequest:
        if self.recommendation_type is not RecommendationType.SIMILAR:
            msg = "recommendation_type must be SIMILAR for the production API"
            raise ValueError(msg)
        max_top_k = resolve_api_max_top_k()
        if self.top_k > max_top_k:
            msg = f"top_k must not exceed {max_top_k}"
            raise ValueError(msg)
        seed = self.seed_product_id.strip()
        if not seed:
            msg = "seed_product_id must not be empty"
            raise ValueError(msg)
        return self


class RecommendationResultItem(BaseModel):
    """One ranked recommendation for API clients."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    product_id: str = Field(min_length=1)
    rank: int = Field(ge=1)
    recommendation_score: float = Field(description="Final recommendation score from the pipeline.")


class RecommendationApiResponse(BaseModel):
    """Recommendation response envelope."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    seed_product_id: str = Field(min_length=1)
    recommendation_type: RecommendationType
    top_k: int = Field(gt=0)
    recommendations: tuple[RecommendationResultItem, ...] = ()
    request_id: str = Field(min_length=1)
    returned_count: int = Field(ge=0)


__all__ = [
    "RecommendationApiRequest",
    "RecommendationApiResponse",
    "RecommendationResultItem",
]
