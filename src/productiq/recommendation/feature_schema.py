"""Recommendation feature schema (Phase 11.4)."""

from __future__ import annotations

import math
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

RECOMMENDATION_FEATURE_SCHEMA_VERSION = "11.4.0"
RECOMMENDATION_FEATURE_ORDER_VERSION = "11.4.0"


def _validate_optional_finite(value: float | None) -> float | None:
    if value is None:
        return None
    if not math.isfinite(value):
        msg = "feature value must be a finite number"
        raise ValueError(msg)
    return value


class CandidateGenerationFeatureGroup(BaseModel):
    """Factual provenance and native generation score from Phase 11.2."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    retrieved_by_vector: bool
    retrieved_by_attribute: bool
    retrieved_by_bm25: bool
    retrieved_by_multiple_sources: bool
    source_count: int = Field(ge=1)
    candidate_generation_score: float | None = None

    @field_validator("candidate_generation_score")
    @classmethod
    def validate_finite_generation_score(cls, value: float | None) -> float | None:
        return _validate_optional_finite(value)


class SimilarityFeatureGroup(BaseModel):
    """Component similarity signals propagated from Phase 11.3 (no fused score)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    semantic_similarity: float | None = None
    lexical_similarity: float | None = None

    @field_validator("semantic_similarity", "lexical_similarity")
    @classmethod
    def validate_finite(cls, value: float | None) -> float | None:
        return _validate_optional_finite(value)


class StructuredMatchFeatureGroup(BaseModel):
    """Structured seed↔candidate overlaps propagated from Phase 11.3 structured similarities."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    brand_match: float | None = None
    brand_normalized_match: float | None = None
    category_gender_match: float | None = None
    product_type_match: float | None = None
    color_overlap: float | None = None
    pattern_overlap: float | None = None
    material_overlap: float | None = None
    fit_overlap: float | None = None
    sleeve_overlap: float | None = None
    neckline_overlap: float | None = None
    product_features_overlap: float | None = None
    style_attributes_overlap: float | None = None

    @field_validator(
        "brand_match",
        "brand_normalized_match",
        "category_gender_match",
        "product_type_match",
        "color_overlap",
        "pattern_overlap",
        "material_overlap",
        "fit_overlap",
        "sleeve_overlap",
        "neckline_overlap",
        "product_features_overlap",
        "style_attributes_overlap",
    )
    @classmethod
    def validate_finite(cls, value: float | None) -> float | None:
        return _validate_optional_finite(value)


class CatalogContextFeatureGroup(BaseModel):
    """Raw catalog economics and seed-relative price deltas when filtering metadata is supplied."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    discount_price_inr: int | None = Field(default=None, ge=0)
    original_price_inr: int | None = Field(default=None, ge=0)
    discount_amount_inr: int | None = Field(default=None, ge=0)
    discount_price_delta_from_seed_inr: int | None = None
    original_price_delta_from_seed_inr: int | None = None


class RecommendationFeatures(BaseModel):
    """Immutable recommendation features for one candidate (not a ranking result)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    product_id: str = Field(min_length=1)
    feature_schema_version: str = Field(
        default=RECOMMENDATION_FEATURE_SCHEMA_VERSION,
        min_length=1,
    )
    generation: CandidateGenerationFeatureGroup
    similarity: SimilarityFeatureGroup
    structured: StructuredMatchFeatureGroup
    catalog: CatalogContextFeatureGroup


ORDERED_RECOMMENDATION_FEATURE_NAMES: tuple[str, ...] = (
    "generation.retrieved_by_vector",
    "generation.retrieved_by_attribute",
    "generation.retrieved_by_bm25",
    "generation.retrieved_by_multiple_sources",
    "generation.source_count",
    "generation.candidate_generation_score",
    "similarity.semantic_similarity",
    "similarity.lexical_similarity",
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
    "catalog.discount_price_inr",
    "catalog.original_price_inr",
    "catalog.discount_amount_inr",
    "catalog.discount_price_delta_from_seed_inr",
    "catalog.original_price_delta_from_seed_inr",
)


def recommendation_features_to_dict(features: RecommendationFeatures) -> dict[str, Any]:
    return features.model_dump(mode="json")


__all__ = [
    "ORDERED_RECOMMENDATION_FEATURE_NAMES",
    "RECOMMENDATION_FEATURE_ORDER_VERSION",
    "RECOMMENDATION_FEATURE_SCHEMA_VERSION",
    "CandidateGenerationFeatureGroup",
    "CatalogContextFeatureGroup",
    "RecommendationFeatures",
    "SimilarityFeatureGroup",
    "StructuredMatchFeatureGroup",
    "recommendation_features_to_dict",
]
