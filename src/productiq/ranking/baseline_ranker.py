"""Deterministic baseline ranker (Phase 10.4)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from productiq.exceptions.base import RankingError
from productiq.ranking.baseline_config import BASELINE_RANKER_VERSION, BaselineRankingConfig
from productiq.ranking.baseline_scoring import compute_baseline_score
from productiq.ranking.config import RankingConfig
from productiq.ranking.contracts import (
    RankedCandidate,
    RankingCandidate,
    RankingRequest,
    RankingResponse,
)
from productiq.ranking.invariants import (
    apply_ranking_top_k,
    deterministic_ranking_sort_key,
    validate_ranking_request_for_ranker,
    validate_ranking_response_invariants,
    validate_unique_ranking_product_ids,
)
from productiq.ranking.normalization_schema import NormalizedRankingFeatures


def _align_candidates_and_features(
    candidates: tuple[RankingCandidate, ...],
    normalized_features: Sequence[NormalizedRankingFeatures],
) -> tuple[tuple[RankingCandidate, NormalizedRankingFeatures], ...]:
    if len(candidates) != len(normalized_features):
        msg = "candidate and normalized feature counts must match"
        raise RankingError(msg)
    validate_unique_ranking_product_ids(candidates)
    feature_ids = [row.product_id for row in normalized_features]
    if len(feature_ids) != len(set(feature_ids)):
        msg = "normalized features must have unique product_id values"
        raise RankingError(msg)
    aligned: list[tuple[RankingCandidate, NormalizedRankingFeatures]] = []
    for candidate, features in zip(candidates, normalized_features, strict=True):
        if features.product_id != candidate.product_id:
            msg = "candidate.product_id must match normalized_features.product_id"
            raise RankingError(msg)
        aligned.append((candidate, features))
    return tuple(aligned)


def rank_candidates(
    *,
    request: RankingRequest,
    normalized_features_by_product_id: Mapping[str, NormalizedRankingFeatures],
    baseline_config: BaselineRankingConfig | None = None,
) -> RankingResponse:
    """Rank pre-filtered candidates using weighted normalized features."""
    config = baseline_config or BaselineRankingConfig()
    validate_ranking_request_for_ranker(request)
    validate_unique_ranking_product_ids(request.candidates)
    if not request.candidates:
        response = RankingResponse(
            ranked_candidates=(),
            requested_top_k=request.top_k,
            config=RankingConfig(ranking_version=config.baseline_version),
        )
        validate_ranking_response_invariants(response)
        return response
    ordered_features = tuple(
        _require_feature_row(normalized_features_by_product_id, candidate.product_id)
        for candidate in request.candidates
    )
    pairs = _align_candidates_and_features(request.candidates, ordered_features)
    scored: list[tuple[RankingCandidate, float]] = []
    for candidate, features in pairs:
        breakdown = compute_baseline_score(features, config=config)
        scored.append((candidate, breakdown.ranking_score))
    scored.sort(
        key=lambda row: deterministic_ranking_sort_key(
            ranking_score=row[1],
            product_id=row[0].product_id,
            config=RankingConfig(
                ranking_version=config.baseline_version,
                tie_break_key=config.tie_break_key,
            ),
        )
    )
    ranked: list[RankedCandidate] = []
    for index, (candidate, score) in enumerate(scored, start=1):
        ranked.append(
            RankedCandidate(
                product_id=candidate.product_id,
                rank=index,
                ranking_score=score,
                candidate=candidate,
            )
        )
    trimmed = apply_ranking_top_k(tuple(ranked), top_k=request.top_k)
    response = RankingResponse(
        ranked_candidates=trimmed,
        requested_top_k=request.top_k,
        config=RankingConfig(
            ranking_version=config.baseline_version or BASELINE_RANKER_VERSION,
            tie_break_key=config.tie_break_key,
        ),
    )
    validate_ranking_response_invariants(response)
    return response


def rank_candidates_with_feature_rows(
    *,
    request: RankingRequest,
    normalized_features: Sequence[NormalizedRankingFeatures],
    baseline_config: BaselineRankingConfig | None = None,
) -> RankingResponse:
    feature_ids = [row.product_id for row in normalized_features]
    if len(feature_ids) != len(set(feature_ids)):
        msg = "normalized features must have unique product_id values"
        raise RankingError(msg)
    feature_map = {row.product_id: row for row in normalized_features}
    return rank_candidates(
        request=request,
        normalized_features_by_product_id=feature_map,
        baseline_config=baseline_config,
    )


def _require_feature_row(
    mapping: Mapping[str, NormalizedRankingFeatures],
    product_id: str,
) -> NormalizedRankingFeatures:
    row = mapping.get(product_id)
    if row is None:
        msg = f"missing normalized features for product_id={product_id!r}"
        raise RankingError(msg)
    return row


__all__ = [
    "rank_candidates",
    "rank_candidates_with_feature_rows",
]
