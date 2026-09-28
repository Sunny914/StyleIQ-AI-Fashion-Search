"""Ranking feature schema (Phase 10.2)."""

from __future__ import annotations

import math
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

RANKING_FEATURE_SCHEMA_VERSION = "10.2.0"


def _validate_optional_finite(value: float | None) -> float | None:
    if value is None:
        return None
    if not math.isfinite(value):
        msg = "feature value must be a finite number"
        raise ValueError(msg)
    return value


class RetrievalFeatureGroup(BaseModel):
    """Raw retrieval signals projected from ``RetrievalCandidate``."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    bm25_score: float | None = None
    bm25_rank: int | None = Field(default=None, ge=1)
    vector_similarity: float | None = None
    vector_rank: int | None = Field(default=None, ge=1)
    rrf_score: float | None = None
    retrieved_by_bm25: bool
    retrieved_by_vector: bool
    retrieved_by_both: bool

    @field_validator("bm25_score", "vector_similarity", "rrf_score")
    @classmethod
    def validate_finite_optional(cls, value: float | None) -> float | None:
        return _validate_optional_finite(value)


class MatchingFeatureGroup(BaseModel):
    """Structured query-constraint vs product matching (diagnostic, not filtering)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    brand_match: bool | None = None
    color_match: bool | None = None
    product_type_match: bool | None = None
    category_gender_match: bool | None = None
    material_match: bool | None = None
    matched_attribute_count: int = Field(ge=0)
    attribute_overlap: float | None = Field(default=None, ge=0.0, le=1.0)
    constraint_match: bool | None = None


class CatalogFeatureGroup(BaseModel):
    """Raw catalog economics when ``FilteringRepresentation`` is supplied to the extractor."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    discount_price_inr: int | None = Field(default=None, ge=0)
    original_price_inr: int | None = Field(default=None, ge=0)
    discount_amount_inr: int | None = Field(default=None, ge=0)


class RankingFeatures(BaseModel):
    """Immutable raw ranking features for one candidate."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    product_id: str = Field(min_length=1)
    feature_schema_version: str = Field(default=RANKING_FEATURE_SCHEMA_VERSION, min_length=1)
    retrieval: RetrievalFeatureGroup
    matching: MatchingFeatureGroup
    catalog: CatalogFeatureGroup


def ranking_features_to_dict(features: RankingFeatures) -> dict[str, Any]:
    """Serialize ranking features to a JSON-compatible dict."""
    return features.model_dump(mode="json")


__all__ = [
    "RANKING_FEATURE_SCHEMA_VERSION",
    "CatalogFeatureGroup",
    "MatchingFeatureGroup",
    "RankingFeatures",
    "RetrievalFeatureGroup",
    "ranking_features_to_dict",
]
