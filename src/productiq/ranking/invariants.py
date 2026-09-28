"""Ranking invariants and deterministic ordering helpers (Phase 10.1, hardened 10.9)."""

from __future__ import annotations

import math

from productiq.exceptions.base import RankingError
from productiq.ranking.config import DEFAULT_TIE_BREAK_KEY, RankingConfig
from productiq.ranking.contracts import (
    RankedCandidate,
    RankingCandidate,
    RankingRequest,
    RankingResponse,
)
from productiq.ranking.normalization_schema import NormalizedRankingFeatures


def validate_unique_ranking_product_ids(candidates: tuple[RankingCandidate, ...]) -> None:
    product_ids = [candidate.product_id for candidate in candidates]
    if len(product_ids) != len(set(product_ids)):
        msg = "ranking candidates must have unique product_id values"
        raise RankingError(msg)


def ranking_output_limit(*, candidate_count: int, top_k: int) -> int:
    if top_k <= 0:
        msg = "top_k must be positive"
        raise RankingError(msg)
    return min(candidate_count, top_k)


def apply_ranking_top_k(
    ranked_candidates: tuple[RankedCandidate, ...],
    *,
    top_k: int,
) -> tuple[RankedCandidate, ...]:
    """Return at most ``top_k`` ranked rows without mutating the input tuple."""
    limit = ranking_output_limit(candidate_count=len(ranked_candidates), top_k=top_k)
    return ranked_candidates[:limit]


def deterministic_ranking_sort_key(
    *,
    ranking_score: float,
    product_id: str,
    config: RankingConfig | None = None,
) -> tuple[float, str]:
    """Primary: higher score first (negated for ascending sort). Secondary: ``product_id``."""
    resolved = config or RankingConfig()
    if resolved.tie_break_key != DEFAULT_TIE_BREAK_KEY:
        msg = f"unsupported tie_break_key: {resolved.tie_break_key!r}"
        raise RankingError(msg)
    return (-ranking_score, product_id)


def assert_ranking_request_inputs_unchanged(
    before: tuple[RankingCandidate, ...],
    after: tuple[RankingCandidate, ...],
) -> None:
    if before != after:
        msg = "ranking input candidate tuple was mutated"
        raise RankingError(msg)


def empty_ranking_response_metadata(*, top_k: int, config: RankingConfig) -> dict[str, object]:
    return {
        "requested_top_k": top_k,
        "returned_candidate_count": 0,
        "ranking_version": config.ranking_version,
    }


def validate_positive_top_k(top_k: int) -> None:
    if top_k <= 0:
        msg = "top_k must be positive"
        raise RankingError(msg)


def validate_unique_normalized_feature_product_ids(
    features: tuple[NormalizedRankingFeatures, ...] | list[NormalizedRankingFeatures],
) -> None:
    product_ids = [row.product_id for row in features]
    if len(product_ids) != len(set(product_ids)):
        msg = "normalized features must have unique product_id values"
        raise RankingError(msg)


def validate_candidate_feature_product_alignment(
    candidates: tuple[RankingCandidate, ...],
    normalized_features: tuple[NormalizedRankingFeatures, ...] | list[NormalizedRankingFeatures],
) -> None:
    if len(candidates) != len(normalized_features):
        msg = "candidate and normalized feature counts must match"
        raise RankingError(msg)
    validate_unique_ranking_product_ids(candidates)
    validate_unique_normalized_feature_product_ids(normalized_features)
    for candidate, features in zip(candidates, normalized_features, strict=True):
        if features.product_id != candidate.product_id:
            msg = "candidate.product_id must match normalized_features.product_id"
            raise RankingError(msg)


def validate_ranking_response_invariants(response: RankingResponse) -> None:
    """Post-condition checks shared by baseline and LTR rankers."""
    validate_positive_top_k(response.requested_top_k)
    if response.returned_candidate_count > response.requested_top_k:
        msg = "returned_candidate_count must not exceed requested_top_k"
        raise RankingError(msg)
    ranks = [row.rank for row in response.ranked_candidates]
    if ranks != sorted(ranks):
        msg = "ranked_candidates must be ordered by ascending rank"
        raise RankingError(msg)
    if ranks and ranks[0] != 1:
        msg = "ranked output must start at rank 1 when non-empty"
        raise RankingError(msg)
    for index, expected_rank in enumerate(ranks, start=1):
        if expected_rank != index:
            msg = "ranked_candidates must use contiguous 1-based ranks"
            raise RankingError(msg)
    product_ids = [row.product_id for row in response.ranked_candidates]
    if len(product_ids) != len(set(product_ids)):
        msg = "ranked output must not duplicate product_id values"
        raise RankingError(msg)
    for row in response.ranked_candidates:
        if not math.isfinite(row.ranking_score):
            msg = "ranking_score must be finite"
            raise RankingError(msg)
        if row.product_id != row.candidate.product_id:
            msg = "RankedCandidate product_id must match embedded candidate"
            raise RankingError(msg)


def validate_ranking_request_for_ranker(request: RankingRequest) -> None:
    validate_positive_top_k(request.top_k)
    validate_unique_ranking_product_ids(request.candidates)


__all__ = [
    "apply_ranking_top_k",
    "assert_ranking_request_inputs_unchanged",
    "deterministic_ranking_sort_key",
    "empty_ranking_response_metadata",
    "ranking_output_limit",
    "validate_candidate_feature_product_alignment",
    "validate_positive_top_k",
    "validate_ranking_request_for_ranker",
    "validate_ranking_response_invariants",
    "validate_unique_normalized_feature_product_ids",
    "validate_unique_ranking_product_ids",
]
