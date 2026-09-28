"""Content similarity contracts (Phase 11.3)."""

from __future__ import annotations

import math
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

CONTENT_SIMILARITY_SCHEMA_VERSION = "11.3.0"


def _validate_optional_finite_similarity(value: float | None) -> float | None:
    if value is None:
        return None
    if not math.isfinite(value):
        msg = "similarity value must be a finite number"
        raise ValueError(msg)
    return value


class ScalarAttributeSimilarity(BaseModel):
    """Pairwise scalar attribute similarity in ``{0.0, 1.0}`` or ``None`` when either side is missing."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    brand: float | None = None
    brand_normalized: float | None = None
    category_gender: float | None = None
    product_type: float | None = None

    @field_validator("brand", "brand_normalized", "category_gender", "product_type")
    @classmethod
    def validate_finite(cls, value: float | None) -> float | None:
        return _validate_optional_finite_similarity(value)


class MultiValueAttributeSimilarity(BaseModel):
    """Jaccard similarities for multi-value product attributes (``None`` when either side missing)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    color: float | None = None
    pattern: float | None = None
    material: float | None = None
    fit: float | None = None
    sleeve: float | None = None
    neckline: float | None = None
    product_features: float | None = None
    style_attributes: float | None = None

    @field_validator(
        "color",
        "pattern",
        "material",
        "fit",
        "sleeve",
        "neckline",
        "product_features",
        "style_attributes",
    )
    @classmethod
    def validate_finite(cls, value: float | None) -> float | None:
        return _validate_optional_finite_similarity(value)


class StructuredProductSimilarity(BaseModel):
    """Structured seed↔candidate attribute similarities (no fused aggregate score)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    scalars: ScalarAttributeSimilarity = Field(default_factory=ScalarAttributeSimilarity)
    multivalue: MultiValueAttributeSimilarity = Field(default_factory=MultiValueAttributeSimilarity)


class ContentSimilarity(BaseModel):
    """Similarity signals between one seed product and one recommendation candidate."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    product_id: str = Field(min_length=1)
    content_similarity_schema_version: str = Field(
        default=CONTENT_SIMILARITY_SCHEMA_VERSION,
        min_length=1,
    )
    semantic_similarity: float | None = Field(
        default=None,
        description="Cosine similarity between catalog embeddings (Phase 4.9 semantics).",
    )
    lexical_similarity: float | None = Field(
        default=None,
        description="BM25 lexical relatedness of seed text to candidate document (not generation score).",
    )
    structured: StructuredProductSimilarity = Field(default_factory=StructuredProductSimilarity)

    @field_validator("product_id")
    @classmethod
    def validate_product_id(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            msg = "product_id must not be empty"
            raise ValueError(msg)
        return stripped

    @field_validator("semantic_similarity", "lexical_similarity")
    @classmethod
    def validate_finite(cls, value: float | None) -> float | None:
        return _validate_optional_finite_similarity(value)


def content_similarity_to_dict(row: ContentSimilarity) -> dict[str, Any]:
    return row.model_dump(mode="json")


__all__ = [
    "CONTENT_SIMILARITY_SCHEMA_VERSION",
    "ContentSimilarity",
    "MultiValueAttributeSimilarity",
    "ScalarAttributeSimilarity",
    "StructuredProductSimilarity",
    "content_similarity_to_dict",
]
