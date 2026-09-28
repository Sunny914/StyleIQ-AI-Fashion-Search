"""Weighted baseline scoring over normalized features (Phase 10.4)."""

from __future__ import annotations

import math
from dataclasses import dataclass

from productiq.exceptions.base import RankingError
from productiq.ranking.baseline_config import BaselineFeatureWeights, BaselineRankingConfig
from productiq.ranking.normalization_schema import NormalizedRankingFeatures


@dataclass(frozen=True)
class BaselineScoreBreakdown:
    """Inspectable weighted contributions for one candidate."""

    product_id: str
    ranking_score: float
    contributions: tuple[tuple[str, float], ...]


def _weighted_term(
    *,
    feature_name: str,
    value: float | None,
    weight: float,
    missing_contribution: float,
) -> tuple[str, float]:
    if weight == 0.0:
        return feature_name, 0.0
    if value is None:
        return feature_name, weight * missing_contribution
    if not math.isfinite(value):
        msg = f"non-finite normalized feature {feature_name!r} for scoring"
        raise RankingError(msg)
    return feature_name, weight * value


def compute_baseline_score(
    features: NormalizedRankingFeatures,
    *,
    config: BaselineRankingConfig,
) -> BaselineScoreBreakdown:
    weights = config.weights
    missing = config.missing_value_contribution
    terms: list[tuple[str, float]] = []
    retrieval = features.retrieval
    matching = features.matching
    catalog = features.catalog
    term_specs: list[tuple[str, float | None, float]] = [
        ("retrieval.bm25_score", retrieval.bm25_score, weights.bm25_score),
        ("retrieval.bm25_rank", retrieval.bm25_rank, weights.bm25_rank),
        ("retrieval.vector_similarity", retrieval.vector_similarity, weights.vector_similarity),
        ("retrieval.vector_rank", retrieval.vector_rank, weights.vector_rank),
        ("retrieval.rrf_score", retrieval.rrf_score, weights.rrf_score),
        ("retrieval.retrieved_by_bm25", retrieval.retrieved_by_bm25, weights.retrieved_by_bm25),
        ("retrieval.retrieved_by_vector", retrieval.retrieved_by_vector, weights.retrieved_by_vector),
        ("retrieval.retrieved_by_both", retrieval.retrieved_by_both, weights.retrieved_by_both),
        ("matching.brand_match", matching.brand_match, weights.brand_match),
        ("matching.color_match", matching.color_match, weights.color_match),
        ("matching.product_type_match", matching.product_type_match, weights.product_type_match),
        ("matching.category_gender_match", matching.category_gender_match, weights.category_gender_match),
        ("matching.material_match", matching.material_match, weights.material_match),
        ("matching.matched_attribute_count", matching.matched_attribute_count, weights.matched_attribute_count),
        ("matching.attribute_overlap", matching.attribute_overlap, weights.attribute_overlap),
        ("matching.constraint_match", matching.constraint_match, weights.constraint_match),
        ("catalog.discount_price_inr", catalog.discount_price_inr, weights.discount_price_inr),
        ("catalog.original_price_inr", catalog.original_price_inr, weights.original_price_inr),
        ("catalog.discount_amount_inr", catalog.discount_amount_inr, weights.discount_amount_inr),
    ]
    score = 0.0
    for name, value, weight in term_specs:
        feature_name, contribution = _weighted_term(
            feature_name=name,
            value=value,
            weight=weight,
            missing_contribution=missing,
        )
        terms.append((feature_name, contribution))
        score += contribution
    if not math.isfinite(score):
        msg = "baseline ranking score must be finite"
        raise RankingError(msg)
    return BaselineScoreBreakdown(
        product_id=features.product_id,
        ranking_score=score,
        contributions=tuple(terms),
    )


def baseline_weights_as_mapping(weights: BaselineFeatureWeights) -> dict[str, float]:
    return weights.model_dump()


__all__ = [
    "BaselineScoreBreakdown",
    "baseline_weights_as_mapping",
    "compute_baseline_score",
]
