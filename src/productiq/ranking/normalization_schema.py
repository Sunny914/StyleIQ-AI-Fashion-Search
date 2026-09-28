"""Normalization output schema (Phase 10.3)."""

from __future__ import annotations

import math
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from productiq.ranking.feature_schema import RANKING_FEATURE_SCHEMA_VERSION, RankingFeatures

NORMALIZATION_SCHEMA_VERSION = "10.3.0"
CONSTANT_FEATURE_NORMALIZED_VALUE = 0.5


def _validate_optional_finite(value: float | None) -> float | None:
    if value is None:
        return None
    if not math.isfinite(value):
        msg = "normalized feature must be a finite number"
        raise ValueError(msg)
    return value


class NormalizedRetrievalFeatureGroup(BaseModel):
    """Query-group normalized retrieval signals (raw values preserved on ``NormalizedRankingFeatures.raw``)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    bm25_score: float | None = None
    bm25_rank: float | None = None
    vector_similarity: float | None = None
    vector_rank: float | None = None
    rrf_score: float | None = None
    retrieved_by_bm25: float | None = Field(default=None, ge=0.0, le=1.0)
    retrieved_by_vector: float | None = Field(default=None, ge=0.0, le=1.0)
    retrieved_by_both: float | None = Field(default=None, ge=0.0, le=1.0)

    @field_validator(
        "bm25_score",
        "bm25_rank",
        "vector_similarity",
        "vector_rank",
        "rrf_score",
        "retrieved_by_bm25",
        "retrieved_by_vector",
        "retrieved_by_both",
    )
    @classmethod
    def validate_finite(cls, value: float | None) -> float | None:
        return _validate_optional_finite(value)


class NormalizedMatchingFeatureGroup(BaseModel):
    """Matching features (binary as 0/1 floats; overlap unchanged)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    brand_match: float | None = Field(default=None, ge=0.0, le=1.0)
    color_match: float | None = Field(default=None, ge=0.0, le=1.0)
    product_type_match: float | None = Field(default=None, ge=0.0, le=1.0)
    category_gender_match: float | None = Field(default=None, ge=0.0, le=1.0)
    material_match: float | None = Field(default=None, ge=0.0, le=1.0)
    matched_attribute_count: float | None = Field(default=None, ge=0.0, le=1.0)
    attribute_overlap: float | None = Field(default=None, ge=0.0, le=1.0)
    constraint_match: float | None = Field(default=None, ge=0.0, le=1.0)

    @field_validator(
        "brand_match",
        "color_match",
        "product_type_match",
        "category_gender_match",
        "material_match",
        "matched_attribute_count",
        "attribute_overlap",
        "constraint_match",
    )
    @classmethod
    def validate_finite(cls, value: float | None) -> float | None:
        return _validate_optional_finite(value)


class NormalizedCatalogFeatureGroup(BaseModel):
    """Query-group min-max normalized catalog numerics."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    discount_price_inr: float | None = None
    original_price_inr: float | None = None
    discount_amount_inr: float | None = None

    @field_validator("discount_price_inr", "original_price_inr", "discount_amount_inr")
    @classmethod
    def validate_finite(cls, value: float | None) -> float | None:
        return _validate_optional_finite(value)


class NormalizedRankingFeatures(BaseModel):
    """Raw plus normalized features for one candidate within a query group."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    product_id: str = Field(min_length=1)
    feature_schema_version: str = Field(default=RANKING_FEATURE_SCHEMA_VERSION, min_length=1)
    normalization_schema_version: str = Field(default=NORMALIZATION_SCHEMA_VERSION, min_length=1)
    raw: RankingFeatures
    retrieval: NormalizedRetrievalFeatureGroup
    matching: NormalizedMatchingFeatureGroup
    catalog: NormalizedCatalogFeatureGroup


def normalized_ranking_features_to_dict(row: NormalizedRankingFeatures) -> dict[str, Any]:
    return row.model_dump(mode="json")


__all__ = [
    "CONSTANT_FEATURE_NORMALIZED_VALUE",
    "NORMALIZATION_SCHEMA_VERSION",
    "NormalizedCatalogFeatureGroup",
    "NormalizedMatchingFeatureGroup",
    "NormalizedRankingFeatures",
    "NormalizedRetrievalFeatureGroup",
    "normalized_ranking_features_to_dict",
]
