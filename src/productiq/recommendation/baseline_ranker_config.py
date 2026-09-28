"""Baseline recommendation ranker configuration (Phase 11.5)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from productiq.recommendation.config import DEFAULT_RECOMMENDATION_TIE_BREAK_KEY

BASELINE_RECOMMENDATION_RANKER_VERSION = "11.5.0"

BASELINE_WEIGHTED_RECOMMENDATION_FEATURE_NAMES: frozenset[str] = frozenset(
    {
        "similarity.semantic_similarity",
        "similarity.lexical_similarity",
        "generation.retrieved_by_multiple_sources",
        "generation.retrieved_by_vector",
        "generation.retrieved_by_attribute",
        "generation.retrieved_by_bm25",
        "structured.brand_match",
        "structured.brand_normalized_match",
        "structured.category_gender_match",
        "structured.product_type_match",
        "structured.color_overlap",
        "structured.pattern_overlap",
        "structured.material_overlap",
        "structured.fit_overlap",
        "structured.sleeve_overlap",
        "structured.neckline_overlap",
        "structured.product_features_overlap",
        "structured.style_attributes_overlap",
    }
)


class BaselineRecommendationFeatureWeights(BaseModel):
    """Explicit hand-authored weights (not learned). Catalog price fields intentionally omitted."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    semantic_similarity: float = Field(default=0.20, ge=0.0)
    lexical_similarity: float = Field(default=0.10, ge=0.0)
    retrieved_by_multiple_sources: float = Field(default=0.05, ge=0.0)
    retrieved_by_vector: float = Field(default=0.03, ge=0.0)
    retrieved_by_attribute: float = Field(default=0.03, ge=0.0)
    retrieved_by_bm25: float = Field(default=0.03, ge=0.0)
    brand_match: float = Field(default=0.12, ge=0.0)
    brand_normalized_match: float = Field(default=0.03, ge=0.0)
    category_gender_match: float = Field(default=0.08, ge=0.0)
    product_type_match: float = Field(default=0.10, ge=0.0)
    color_overlap: float = Field(default=0.08, ge=0.0)
    pattern_overlap: float = Field(default=0.03, ge=0.0)
    material_overlap: float = Field(default=0.04, ge=0.0)
    fit_overlap: float = Field(default=0.03, ge=0.0)
    sleeve_overlap: float = Field(default=0.02, ge=0.0)
    neckline_overlap: float = Field(default=0.02, ge=0.0)
    product_features_overlap: float = Field(default=0.03, ge=0.0)
    style_attributes_overlap: float = Field(default=0.03, ge=0.0)

    def weight_for_feature_name(self, feature_name: str) -> float:
        if feature_name not in BASELINE_WEIGHTED_RECOMMENDATION_FEATURE_NAMES:
            msg = f"no baseline weight configured for feature {feature_name!r}"
            raise ValueError(msg)
        prefix, _, field = feature_name.partition(".")
        del prefix
        return float(getattr(self, field))


class BaselineRecommendationRankerConfig(BaseModel):
    """Frozen deterministic baseline recommendation ranker settings."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    ranker_version: str = Field(default=BASELINE_RECOMMENDATION_RANKER_VERSION, min_length=1)
    weights: BaselineRecommendationFeatureWeights = Field(
        default_factory=BaselineRecommendationFeatureWeights
    )
    missing_feature_contribution: float = Field(
        default=0.0,
        description=(
            "Additive score when a weighted feature value is None "
            "(weight * missing_feature_contribution; feature object unchanged)."
        ),
    )
    tie_break_key: Literal["product_id"] = Field(default=DEFAULT_RECOMMENDATION_TIE_BREAK_KEY)

    @model_validator(mode="after")
    def validate_positive_total_weight(self) -> BaselineRecommendationRankerConfig:
        total = sum(self.weights.model_dump().values())
        if total <= 0.0:
            msg = "baseline recommendation feature weights must sum to a positive value"
            raise ValueError(msg)
        return self


def ordered_baseline_weighted_feature_names() -> tuple[str, ...]:
    """Stable scoring order (generation provenance, similarity, structured)."""
    return tuple(sorted(BASELINE_WEIGHTED_RECOMMENDATION_FEATURE_NAMES))


__all__ = [
    "BASELINE_RECOMMENDATION_RANKER_VERSION",
    "BASELINE_WEIGHTED_RECOMMENDATION_FEATURE_NAMES",
    "BaselineRecommendationFeatureWeights",
    "BaselineRecommendationRankerConfig",
    "ordered_baseline_weighted_feature_names",
]
