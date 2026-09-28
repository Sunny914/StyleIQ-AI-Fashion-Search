"""Deterministic baseline recommendation ranker (Phase 11.5)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from productiq.exceptions.base import RecommendationError
from productiq.recommendation.baseline_ranker_config import BaselineRecommendationRankerConfig
from productiq.recommendation.baseline_scoring import compute_baseline_recommendation_score
from productiq.recommendation.config import RecommendationConfig
from productiq.recommendation.contracts import (
    RankedRecommendation,
    RecommendationCandidate,
    RecommendationRequest,
    RecommendationResponse,
)
from productiq.recommendation.feature_schema import RecommendationFeatures
from productiq.recommendation.invariants import (
    deterministic_recommendation_sort_key,
    recommendation_output_limit,
    validate_positive_top_k,
    validate_recommendation_request_for_pipeline,
    validate_recommendation_response_invariants,
    validate_seed_product_excluded,
    validate_unique_recommendation_product_ids,
)


def _validate_unique_feature_product_ids(features: Sequence[RecommendationFeatures]) -> None:
    product_ids = [row.product_id for row in features]
    if len(product_ids) != len(set(product_ids)):
        msg = "recommendation features must have unique product_id values"
        raise RecommendationError(msg)


def _exclude_seed_features(
    features: Sequence[RecommendationFeatures],
    *,
    seed_product_id: str | None,
) -> tuple[RecommendationFeatures, ...]:
    if seed_product_id is None:
        return tuple(features)
    return tuple(row for row in features if row.product_id != seed_product_id)


class BaselineRecommendationRanker:
    """Hand-authored weighted sum ranker over Phase 11.4 features (not LTR)."""

    def __init__(self, *, config: BaselineRecommendationRankerConfig | None = None) -> None:
        self._config = config or BaselineRecommendationRankerConfig()

    @property
    def config(self) -> BaselineRecommendationRankerConfig:
        return self._config

    def rank(
        self,
        features: Sequence[RecommendationFeatures],
        *,
        top_k: int,
        candidates_by_product_id: Mapping[str, RecommendationCandidate] | None = None,
        seed_product_id: str | None = None,
        recommendation_config: RecommendationConfig | None = None,
    ) -> tuple[RankedRecommendation, ...]:
        return rank_recommendations(
            features,
            top_k=top_k,
            config=self._config,
            candidates_by_product_id=candidates_by_product_id,
            seed_product_id=seed_product_id,
            recommendation_config=recommendation_config,
        )


def rank_recommendations(
    features: Sequence[RecommendationFeatures],
    *,
    top_k: int,
    config: BaselineRecommendationRankerConfig | None = None,
    candidates_by_product_id: Mapping[str, RecommendationCandidate] | None = None,
    seed_product_id: str | None = None,
    recommendation_config: RecommendationConfig | None = None,
) -> tuple[RankedRecommendation, ...]:
    """Score, sort, truncate to top_k, and assign contiguous ranks."""
    resolved_config = config or BaselineRecommendationRankerConfig()
    resolved_recommendation_config = recommendation_config or RecommendationConfig()
    validate_positive_top_k(top_k)
    if top_k > resolved_recommendation_config.max_top_k:
        msg = "top_k must not exceed config.max_top_k"
        raise RecommendationError(msg)
    if resolved_recommendation_config.tie_break_key != resolved_config.tie_break_key:
        msg = "baseline ranker tie_break_key must match RecommendationConfig.tie_break_key"
        raise RecommendationError(msg)

    if not features:
        return ()

    _validate_unique_feature_product_ids(features)
    eligible = _exclude_seed_features(features, seed_product_id=seed_product_id)

    scored: list[tuple[RecommendationFeatures, float]] = []
    for row in eligible:
        breakdown = compute_baseline_recommendation_score(row, config=resolved_config)
        scored.append((row, breakdown.recommendation_score))

    scored.sort(
        key=lambda item: deterministic_recommendation_sort_key(
            recommendation_score=item[1],
            product_id=item[0].product_id,
            config=resolved_recommendation_config,
        )
    )

    limit = recommendation_output_limit(recommendation_count=len(scored), top_k=top_k)
    trimmed = scored[:limit]

    ranked: list[RankedRecommendation] = []
    for rank_index, (feature_row, score) in enumerate(trimmed, start=1):
        candidate = (
            candidates_by_product_id.get(feature_row.product_id)
            if candidates_by_product_id is not None
            else None
        )
        if candidate is not None and candidate.product_id != feature_row.product_id:
            msg = "candidate.product_id must match feature product_id"
            raise RecommendationError(msg)
        ranked.append(
            RankedRecommendation(
                product_id=feature_row.product_id,
                rank=rank_index,
                recommendation_score=score,
                candidate=candidate,
            )
        )

    result = tuple(ranked)
    validate_unique_recommendation_product_ids(result)
    if seed_product_id is not None:
        validate_seed_product_excluded(
            seed_product_id=seed_product_id,
            recommendations=result,
        )
    return result


def rank_recommendations_for_request(
    request: RecommendationRequest,
    features: Sequence[RecommendationFeatures],
    *,
    config: BaselineRecommendationRankerConfig | None = None,
    candidates_by_product_id: Mapping[str, RecommendationCandidate] | None = None,
) -> RecommendationResponse:
    """Build a contract-valid ``RecommendationResponse`` from ranked features."""
    validate_recommendation_request_for_pipeline(request)
    recommendations = rank_recommendations(
        features,
        top_k=request.top_k,
        config=config,
        candidates_by_product_id=candidates_by_product_id,
        seed_product_id=request.seed_product_id,
        recommendation_config=request.config,
    )
    response = RecommendationResponse(
        seed_product_id=request.seed_product_id,
        recommendation_type=request.recommendation_type,
        recommendations=recommendations,
        requested_top_k=request.top_k,
        config=request.config,
    )
    validate_recommendation_response_invariants(response)
    return response


__all__ = [
    "BaselineRecommendationRanker",
    "rank_recommendations",
    "rank_recommendations_for_request",
]
