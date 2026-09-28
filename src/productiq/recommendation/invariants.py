"""Recommendation invariants and deterministic ordering helpers (Phase 11.1)."""

from __future__ import annotations

import math
from itertools import pairwise

from productiq.exceptions.base import RecommendationError
from productiq.recommendation.config import (
    DEFAULT_RECOMMENDATION_TIE_BREAK_KEY,
    RecommendationConfig,
)
from productiq.recommendation.contracts import (
    IMPLEMENTED_RECOMMENDATION_TYPES,
    RankedRecommendation,
    RecommendationCandidate,
    RecommendationRequest,
    RecommendationResponse,
    RecommendationType,
)


def validate_positive_top_k(top_k: int) -> None:
    if top_k <= 0:
        msg = "top_k must be positive"
        raise RecommendationError(msg)


def validate_recommendation_type_implemented(recommendation_type: RecommendationType) -> None:
    if recommendation_type not in IMPLEMENTED_RECOMMENDATION_TYPES:
        msg = f"recommendation type {recommendation_type.value!r} is not implemented"
        raise RecommendationError(msg)


def validate_unique_recommendation_product_ids(
    recommendations: tuple[RankedRecommendation, ...],
) -> None:
    product_ids = [row.product_id for row in recommendations]
    if len(product_ids) != len(set(product_ids)):
        msg = "recommendation output must not duplicate product_id values"
        raise RecommendationError(msg)


def validate_seed_product_excluded(
    *,
    seed_product_id: str,
    recommendations: tuple[RankedRecommendation, ...],
) -> None:
    if seed_product_id in {row.product_id for row in recommendations}:
        msg = "seed product must not appear in recommendations"
        raise RecommendationError(msg)


def validate_unique_candidate_product_ids(
    candidates: tuple[RecommendationCandidate, ...],
) -> None:
    product_ids = [candidate.product_id for candidate in candidates]
    if len(product_ids) != len(set(product_ids)):
        msg = "recommendation candidates must have unique product_id values"
        raise RecommendationError(msg)


def recommendation_output_limit(*, recommendation_count: int, top_k: int) -> int:
    validate_positive_top_k(top_k)
    return min(recommendation_count, top_k)


def apply_recommendation_top_k(
    recommendations: tuple[RankedRecommendation, ...],
    *,
    top_k: int,
) -> tuple[RankedRecommendation, ...]:
    """Return at most ``top_k`` recommendation rows without mutating the input tuple."""
    limit = recommendation_output_limit(recommendation_count=len(recommendations), top_k=top_k)
    return recommendations[:limit]


def deterministic_recommendation_sort_key(
    *,
    recommendation_score: float,
    product_id: str,
    config: RecommendationConfig | None = None,
) -> tuple[float, str]:
    """Primary: higher score first (negated for ascending sort). Secondary: ``product_id``."""
    resolved = config or RecommendationConfig()
    if resolved.tie_break_key != DEFAULT_RECOMMENDATION_TIE_BREAK_KEY:
        msg = f"unsupported tie_break_key: {resolved.tie_break_key!r}"
        raise RecommendationError(msg)
    return (-recommendation_score, product_id)


def validate_deterministic_recommendation_ordering(
    recommendations: tuple[RankedRecommendation, ...],
    *,
    config: RecommendationConfig | None = None,
) -> None:
    """When scores tie, product_id must increase with rank (stable tie-break)."""
    resolved = config or RecommendationConfig()
    if len(recommendations) < 2:
        return
    for previous, current in pairwise(recommendations):
        if previous.recommendation_score == current.recommendation_score:
            if previous.product_id >= current.product_id:
                msg = "equal recommendation_score rows must be ordered by ascending product_id"
                raise RecommendationError(msg)
        elif previous.recommendation_score < current.recommendation_score:
            msg = "recommendations must be ordered by descending recommendation_score"
            raise RecommendationError(msg)
    _ = resolved  # config reserved for future tie-break keys


def assert_recommendation_request_inputs_unchanged(
    before: RecommendationRequest,
    after: RecommendationRequest,
) -> None:
    if before != after:
        msg = "recommendation request was mutated"
        raise RecommendationError(msg)


def validate_ranked_recommendation_candidate_alignment(
    row: RankedRecommendation,
) -> None:
    if row.candidate is not None and row.product_id != row.candidate.product_id:
        msg = "RankedRecommendation product_id must match embedded candidate"
        raise RecommendationError(msg)


def validate_recommendation_response_invariants(response: RecommendationResponse) -> None:
    """Post-condition checks for recommendation responses."""
    validate_positive_top_k(response.requested_top_k)
    if response.returned_recommendation_count > response.requested_top_k:
        msg = "returned_recommendation_count must not exceed requested_top_k"
        raise RecommendationError(msg)
    ranks = [row.rank for row in response.recommendations]
    if ranks != sorted(ranks):
        msg = "recommendations must be ordered by ascending rank"
        raise RecommendationError(msg)
    if ranks and ranks[0] != 1:
        msg = "recommendation output must start at rank 1 when non-empty"
        raise RecommendationError(msg)
    for index, expected_rank in enumerate(ranks, start=1):
        if expected_rank != index:
            msg = "recommendations must use contiguous 1-based ranks"
            raise RecommendationError(msg)
    validate_unique_recommendation_product_ids(response.recommendations)
    validate_seed_product_excluded(
        seed_product_id=response.seed_product_id,
        recommendations=response.recommendations,
    )
    for row in response.recommendations:
        if not math.isfinite(row.recommendation_score):
            msg = "recommendation_score must be finite"
            raise RecommendationError(msg)
        validate_ranked_recommendation_candidate_alignment(row)
    validate_deterministic_recommendation_ordering(
        response.recommendations,
        config=response.config,
    )


def validate_recommendation_request_for_pipeline(request: RecommendationRequest) -> None:
    validate_positive_top_k(request.top_k)
    if request.top_k > request.config.max_top_k:
        msg = "top_k must not exceed config.max_top_k"
        raise RecommendationError(msg)


__all__ = [
    "apply_recommendation_top_k",
    "assert_recommendation_request_inputs_unchanged",
    "deterministic_recommendation_sort_key",
    "recommendation_output_limit",
    "validate_deterministic_recommendation_ordering",
    "validate_positive_top_k",
    "validate_ranked_recommendation_candidate_alignment",
    "validate_recommendation_request_for_pipeline",
    "validate_recommendation_response_invariants",
    "validate_recommendation_type_implemented",
    "validate_seed_product_excluded",
    "validate_unique_candidate_product_ids",
    "validate_unique_recommendation_product_ids",
]
