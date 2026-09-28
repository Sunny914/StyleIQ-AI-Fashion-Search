"""Weighted baseline recommendation scoring (Phase 11.5)."""

from __future__ import annotations

import math

from pydantic import BaseModel, ConfigDict, Field, field_validator

from productiq.exceptions.base import RecommendationError
from productiq.recommendation.baseline_ranker_config import (
    BaselineRecommendationRankerConfig,
    ordered_baseline_weighted_feature_names,
)
from productiq.recommendation.feature_schema import RecommendationFeatures


class RecommendationScoreContribution(BaseModel):
    """One weighted term in the baseline recommendation score."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    feature_name: str = Field(min_length=1)
    feature_value: float | None = None
    weight: float = Field(ge=0.0)
    contribution: float


class BaselineRecommendationScoreBreakdown(BaseModel):
    """Inspectable weighted contributions for one candidate."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    product_id: str = Field(min_length=1)
    recommendation_score: float
    contributions: tuple[RecommendationScoreContribution, ...]

    @field_validator("recommendation_score")
    @classmethod
    def validate_finite_score(cls, value: float) -> float:
        if not math.isfinite(value):
            msg = "recommendation_score must be a finite number"
            raise ValueError(msg)
        return value


def _raw_feature_value(
    features: RecommendationFeatures,
    feature_name: str,
) -> bool | int | float | None:
    prefix, _, field = feature_name.partition(".")
    if not field:
        msg = f"invalid feature name: {feature_name!r}"
        raise RecommendationError(msg)
    if prefix == "generation":
        value = getattr(features.generation, field)
    elif prefix == "similarity":
        value = getattr(features.similarity, field)
    elif prefix == "structured":
        value = getattr(features.structured, field)
    elif prefix == "catalog":
        value = getattr(features.catalog, field)
    else:
        msg = f"unknown feature group prefix: {prefix!r}"
        raise RecommendationError(msg)
    if isinstance(value, (bool, int, float)) or value is None:
        return value
    msg = f"unsupported feature value type for {feature_name!r}"
    raise RecommendationError(msg)


def _numeric_feature_value(raw: bool | float | None) -> float | None:
    if raw is None:
        return None
    if isinstance(raw, bool):
        return 1.0 if raw else 0.0
    if isinstance(raw, int):
        return float(raw)
    if not math.isfinite(raw):
        msg = "non-finite feature value for baseline scoring"
        raise RecommendationError(msg)
    return raw


def _weighted_contribution(
    *,
    feature_name: str,
    value: float | None,
    weight: float,
    missing_contribution: float,
) -> RecommendationScoreContribution:
    if weight == 0.0:
        return RecommendationScoreContribution(
            feature_name=feature_name,
            feature_value=value,
            weight=weight,
            contribution=0.0,
        )
    if value is None:
        return RecommendationScoreContribution(
            feature_name=feature_name,
            feature_value=None,
            weight=weight,
            contribution=weight * missing_contribution,
        )
    contribution = weight * value
    if not math.isfinite(contribution):
        msg = f"non-finite contribution for feature {feature_name!r}"
        raise RecommendationError(msg)
    return RecommendationScoreContribution(
        feature_name=feature_name,
        feature_value=value,
        weight=weight,
        contribution=contribution,
    )


def compute_baseline_recommendation_score(
    features: RecommendationFeatures,
    *,
    config: BaselineRecommendationRankerConfig | None = None,
) -> BaselineRecommendationScoreBreakdown:
    """Compute sum(weight × value) with missing values contributing zero by default."""
    resolved = config or BaselineRecommendationRankerConfig()
    weights = resolved.weights
    missing = resolved.missing_feature_contribution
    contributions: list[RecommendationScoreContribution] = []
    score = 0.0
    for feature_name in ordered_baseline_weighted_feature_names():
        weight = weights.weight_for_feature_name(feature_name)
        numeric = _numeric_feature_value(_raw_feature_value(features, feature_name))
        term = _weighted_contribution(
            feature_name=feature_name,
            value=numeric,
            weight=weight,
            missing_contribution=missing,
        )
        contributions.append(term)
        score += term.contribution
    if not math.isfinite(score):
        msg = "baseline recommendation score must be finite"
        raise RecommendationError(msg)
    return BaselineRecommendationScoreBreakdown(
        product_id=features.product_id,
        recommendation_score=score,
        contributions=tuple(contributions),
    )


def score_recommendation_features(
    features: RecommendationFeatures,
    *,
    config: BaselineRecommendationRankerConfig | None = None,
) -> BaselineRecommendationScoreBreakdown:
    """Score one feature row (alias for compute_baseline_recommendation_score)."""
    resolved = config or BaselineRecommendationRankerConfig()
    return compute_baseline_recommendation_score(features, config=resolved)


def breakdown_contribution_sum(breakdown: BaselineRecommendationScoreBreakdown) -> float:
    return sum(row.contribution for row in breakdown.contributions)


__all__ = [
    "BaselineRecommendationScoreBreakdown",
    "RecommendationScoreContribution",
    "breakdown_contribution_sum",
    "compute_baseline_recommendation_score",
    "score_recommendation_features",
]
