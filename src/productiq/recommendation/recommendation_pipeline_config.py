"""Recommendation pipeline configuration (Phase 11.8)."""

from __future__ import annotations

from dataclasses import dataclass

from productiq.exceptions.base import RecommendationError
from productiq.recommendation.contracts import RecommendationResponse

RECOMMENDATION_PIPELINE_VERSION = "11.8.0"


def validate_recommendation_pool_against_request(
    *,
    candidate_pool_top_k: int,
    requested_top_k: int,
) -> None:
    """Ensure the candidate pool is deep enough for the final recommendation cap."""
    if candidate_pool_top_k < 1:
        msg = "candidate_pool_top_k must be positive"
        raise RecommendationError(msg)
    if requested_top_k < 1:
        msg = "requested top_k must be positive"
        raise RecommendationError(msg)
    if candidate_pool_top_k < requested_top_k:
        msg = "candidate_pool_top_k must be greater than or equal to requested top_k"
        raise RecommendationError(msg)


@dataclass(frozen=True)
class RecommendationPipelineExecutionMetadata:
    """Optional non-identity execution counters (deterministic given pipeline inputs)."""

    candidate_count: int
    ranked_count: int
    selected_count: int
    generator_failures: tuple[str, ...] = ()
    observations: tuple[str, ...] = ()


@dataclass(frozen=True)
class RecommendationPipelineResult:
    response: RecommendationResponse
    execution: RecommendationPipelineExecutionMetadata


__all__ = [
    "RECOMMENDATION_PIPELINE_VERSION",
    "RecommendationPipelineExecutionMetadata",
    "RecommendationPipelineResult",
    "validate_recommendation_pool_against_request",
]
