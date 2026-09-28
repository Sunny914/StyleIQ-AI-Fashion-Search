"""Recommendation layer configuration (Phase 11.1)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

DEFAULT_RECOMMENDATION_CONTRACT_VERSION = "11.2.0"
DEFAULT_RECOMMENDATION_TIE_BREAK_KEY: Literal["product_id"] = "product_id"
DEFAULT_MAX_RECOMMENDATION_TOP_K = 100
DEFAULT_CANDIDATE_POOL_TOP_K = 50
DEFAULT_MAX_CANDIDATE_POOL_TOP_K = 200
DEFAULT_CANDIDATE_GENERATION_VERSION = "11.2.0"


class RecommendationCandidateGenerationConfig(BaseModel):
    """Per-generator candidate pool settings (distinct from final ``RecommendationRequest.top_k``)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    candidate_generation_version: str = Field(
        default=DEFAULT_CANDIDATE_GENERATION_VERSION,
        min_length=1,
    )
    candidate_pool_top_k: int = Field(
        default=DEFAULT_CANDIDATE_POOL_TOP_K,
        gt=0,
        description="Maximum candidates returned by each enabled generator before union.",
    )
    max_candidate_pool_top_k: int = Field(
        default=DEFAULT_MAX_CANDIDATE_POOL_TOP_K,
        gt=0,
        description="Upper bound validated against candidate_pool_top_k.",
    )
    enable_vector_generator: bool = True
    enable_attribute_generator: bool = True
    enable_bm25_generator: bool = True
    continue_on_generator_failure: bool = Field(
        default=False,
        description="When False, the first unexpected generator error fails the pipeline.",
    )

    @model_validator(mode="after")
    def validate_pool_bounds(self) -> RecommendationCandidateGenerationConfig:
        if self.candidate_pool_top_k > self.max_candidate_pool_top_k:
            msg = "candidate_pool_top_k must not exceed max_candidate_pool_top_k"
            raise ValueError(msg)
        return self


class RecommendationConfig(BaseModel):
    """Frozen recommendation contract metadata."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    recommendation_contract_version: str = Field(
        default=DEFAULT_RECOMMENDATION_CONTRACT_VERSION,
        min_length=1,
        description="Recommendation contract / orchestration version label.",
    )
    max_top_k: int = Field(
        default=DEFAULT_MAX_RECOMMENDATION_TOP_K,
        gt=0,
        description="Upper bound for RecommendationRequest.top_k at the contract layer.",
    )
    tie_break_key: Literal["product_id"] = Field(
        default=DEFAULT_RECOMMENDATION_TIE_BREAK_KEY,
        description="Stable secondary key when recommendation scores tie (deterministic ordering).",
    )
    candidate_generation: RecommendationCandidateGenerationConfig = Field(
        default_factory=RecommendationCandidateGenerationConfig,
    )


__all__ = [
    "DEFAULT_CANDIDATE_GENERATION_VERSION",
    "DEFAULT_CANDIDATE_POOL_TOP_K",
    "DEFAULT_MAX_CANDIDATE_POOL_TOP_K",
    "DEFAULT_MAX_RECOMMENDATION_TOP_K",
    "DEFAULT_RECOMMENDATION_CONTRACT_VERSION",
    "DEFAULT_RECOMMENDATION_TIE_BREAK_KEY",
    "RecommendationCandidateGenerationConfig",
    "RecommendationConfig",
]
