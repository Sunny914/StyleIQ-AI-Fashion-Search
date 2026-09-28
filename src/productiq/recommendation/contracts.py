"""Recommendation layer contracts (Phase 11.1)."""

from __future__ import annotations

import math
from enum import StrEnum
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator

from productiq.recommendation.config import RecommendationConfig
from productiq.representation.query_contract import QueryFilterConstraints


class RecommendationType(StrEnum):
    """Domain recommendation modes (not all are implemented in Phase 11.1)."""

    SIMILAR = "similar"
    ALTERNATIVE = "alternative"
    COMPLEMENTARY = "complementary"
    PERSONALIZED = "personalized"


SUPPORTED_RECOMMENDATION_TYPES: frozenset[RecommendationType] = frozenset(RecommendationType)

# Phase 11.8 wires SIMILAR through the production pipeline (11.2–11.6).
IMPLEMENTED_RECOMMENDATION_TYPES: frozenset[RecommendationType] = frozenset(
    {RecommendationType.SIMILAR},
)


class RecommendationCandidateSource(StrEnum):
    """Provenance for a recommendation candidate prior to final ranking."""

    VECTOR = "vector"
    ATTRIBUTE = "attribute"
    BM25 = "bm25"
    POPULARITY = "popularity"
    BEHAVIORAL = "behavioral"


class RecommendationRequest(BaseModel):
    """Recommendation intent from a seed product (not retrieval mechanics)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    seed_product_id: str = Field(min_length=1)
    recommendation_type: RecommendationType
    top_k: int = Field(gt=0, description="Maximum recommendations to return.")
    filters: QueryFilterConstraints | None = None
    config: RecommendationConfig = Field(default_factory=RecommendationConfig)

    @field_validator("seed_product_id")
    @classmethod
    def validate_seed_product_id(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            msg = "seed_product_id must not be empty"
            raise ValueError(msg)
        return stripped

    @model_validator(mode="after")
    def validate_top_k_within_config(self) -> Self:
        if self.top_k > self.config.max_top_k:
            msg = "top_k must not exceed config.max_top_k"
            raise ValueError(msg)
        return self


class RecommendationCandidate(BaseModel):
    """One product from candidate generation (generation score ≠ final recommendation score)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    product_id: str = Field(min_length=1)
    sources: tuple[RecommendationCandidateSource, ...] = Field(
        min_length=1,
        description="Deterministic ordered provenance (sorted by source value).",
    )
    candidate_generation_score: float | None = Field(
        default=None,
        description=(
            "Score from one generator per merge policy; not comparable across source kinds. "
            "Not the final recommendation_score."
        ),
    )

    @field_validator("product_id")
    @classmethod
    def validate_product_id(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            msg = "product_id must not be empty"
            raise ValueError(msg)
        return stripped

    @field_validator("candidate_generation_score")
    @classmethod
    def validate_finite_generation_score(cls, value: float | None) -> float | None:
        if value is not None and not math.isfinite(value):
            msg = "candidate_generation_score must be a finite number when present"
            raise ValueError(msg)
        return value

    @model_validator(mode="after")
    def validate_sources(self) -> Self:
        ordered = tuple(sorted(self.sources, key=lambda item: item.value))
        if len(ordered) != len(set(ordered)):
            msg = "sources must not contain duplicates"
            raise ValueError(msg)
        if ordered != self.sources:
            msg = "sources must be sorted deterministically by source value"
            raise ValueError(msg)
        return self


class RecommendationGeneratorFailureRecord(BaseModel):
    """Observed generator failure when partial candidate generation is enabled."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    generator_name: str = Field(min_length=1)
    error_message: str = Field(min_length=1)


class RecommendationCandidateGenerationResult(BaseModel):
    """Output of Phase 11.2 candidate generation (not ranked recommendations)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    seed_product_id: str = Field(min_length=1)
    recommendation_type: RecommendationType
    candidates: tuple[RecommendationCandidate, ...] = ()
    candidate_pool_top_k: int = Field(gt=0)
    config: RecommendationConfig = Field(default_factory=RecommendationConfig)
    generator_failures: tuple[RecommendationGeneratorFailureRecord, ...] = ()

    @computed_field  # type: ignore[prop-decorator]
    @property
    def returned_candidate_count(self) -> int:
        return len(self.candidates)


class RankedRecommendation(BaseModel):
    """One product after recommendation ranking (ranker not implemented in Phase 11.1)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    product_id: str = Field(min_length=1)
    rank: int = Field(ge=1, description="1-based position in the recommendation output order.")
    recommendation_score: float = Field(
        description="Finite final recommendation score (distinct from candidate_generation_score).",
    )
    candidate: RecommendationCandidate | None = None

    @field_validator("product_id")
    @classmethod
    def validate_product_id(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            msg = "product_id must not be empty"
            raise ValueError(msg)
        return stripped

    @field_validator("recommendation_score")
    @classmethod
    def validate_finite_recommendation_score(cls, value: float) -> float:
        if not math.isfinite(value):
            msg = "recommendation_score must be a finite number"
            raise ValueError(msg)
        return value

    @model_validator(mode="after")
    def validate_candidate_identity(self) -> Self:
        if self.candidate is not None and self.product_id != self.candidate.product_id:
            msg = "RankedRecommendation.product_id must match candidate.product_id"
            raise ValueError(msg)
        return self


class RecommendationResponse(BaseModel):
    """Complete recommendation result with auditable metadata."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    seed_product_id: str = Field(min_length=1)
    recommendation_type: RecommendationType
    recommendations: tuple[RankedRecommendation, ...] = ()
    requested_top_k: int = Field(gt=0)
    config: RecommendationConfig = Field(default_factory=RecommendationConfig)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def returned_recommendation_count(self) -> int:
        return len(self.recommendations)

    @field_validator("seed_product_id")
    @classmethod
    def validate_seed_product_id(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            msg = "seed_product_id must not be empty"
            raise ValueError(msg)
        return stripped

    @model_validator(mode="after")
    def validate_recommendation_output(self) -> Self:
        if self.returned_recommendation_count > self.requested_top_k:
            msg = "returned_recommendation_count must not exceed requested_top_k"
            raise ValueError(msg)
        ranks = [row.rank for row in self.recommendations]
        if ranks != sorted(ranks):
            msg = "recommendations must be ordered by ascending rank"
            raise ValueError(msg)
        if ranks and ranks[0] != 1:
            msg = "recommendation output must start at rank 1 when non-empty"
            raise ValueError(msg)
        for index, expected_rank in enumerate(ranks, start=1):
            if expected_rank != index:
                msg = "recommendations must use contiguous 1-based ranks"
                raise ValueError(msg)
        product_ids = [row.product_id for row in self.recommendations]
        if len(product_ids) != len(set(product_ids)):
            msg = "recommendation output must not duplicate product_id values"
            raise ValueError(msg)
        if self.seed_product_id in product_ids:
            msg = "seed product must not appear in recommendations"
            raise ValueError(msg)
        return self


def recommendation_request_to_dict(request: RecommendationRequest) -> dict[str, Any]:
    """Serialize a recommendation request to a JSON-compatible dict."""
    return request.model_dump(mode="json")


def recommendation_response_to_dict(response: RecommendationResponse) -> dict[str, Any]:
    """Serialize a recommendation response to a JSON-compatible dict."""
    return response.model_dump(mode="json")


__all__ = [
    "IMPLEMENTED_RECOMMENDATION_TYPES",
    "SUPPORTED_RECOMMENDATION_TYPES",
    "RankedRecommendation",
    "RecommendationCandidate",
    "RecommendationCandidateGenerationResult",
    "RecommendationCandidateSource",
    "RecommendationGeneratorFailureRecord",
    "RecommendationRequest",
    "RecommendationResponse",
    "RecommendationType",
    "recommendation_request_to_dict",
    "recommendation_response_to_dict",
]
