"""Query-side representation contract aligned with product representations (Phase 3.8)."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator, model_validator
from pydantic import ValidationError as PydanticValidationError

from productiq.exceptions.base import QueryRepresentationError
from productiq.representation.ontology import MULTI_VALUE_REPRESENTATION_FIELDS
from productiq.representation.schema import _validate_multivalue_field
from productiq.representation.validators import validate_category_gender

QUERY_CONSTRAINT_MULTI_VALUE_FIELDS: frozenset[str] = MULTI_VALUE_REPRESENTATION_FIELDS

# Query constraint fields aligned with filterable product metadata facets (contract mapping only).
QUERY_TO_FILTERING_FACET_FIELDS: frozenset[str] = frozenset(
    {
        "brand",
        "brand_normalized",
        "category_gender",
        "product_type",
        "color",
        "pattern",
        "material",
        "fit",
        "sleeve",
        "neckline",
        "product_features",
        "style_attributes",
    }
)

QUERY_TO_FILTERING_PRICE_BOUND_FIELDS: frozenset[str] = frozenset(
    {"min_discount_price_inr", "max_discount_price_inr"}
)

# Product-side metadata fields intentionally excluded from query constraints.
QUERY_CONSTRAINT_EXCLUDED_PRODUCT_FIELDS: frozenset[str] = frozenset(
    {
        "product_id",
        "source",
        "color_raw",
        "color_is_coded",
        "discount_price_inr",
        "original_price_inr",
        "price_anomaly",
    }
)

QUERY_REPRESENTATION_FIELD_ORDER: tuple[str, ...] = (
    "query_text",
    "constraints",
    "lexical_intent",
    "semantic_intent",
)


def normalize_query_text(query_text: str) -> str:
    """Normalize user query text deterministically (no semantic rewriting)."""
    normalized = re.sub(r"\s+", " ", query_text.strip())
    if not normalized:
        msg = "query_text must not be empty"
        raise QueryRepresentationError(msg)
    return normalized


class QueryFilterConstraints(BaseModel):
    """Optional hard-filter constraints aligned with product filtering metadata."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    brand: str | None = None
    brand_normalized: str | None = None
    category_gender: str | None = None
    product_type: str | None = None
    color: list[str] | None = None
    pattern: list[str] | None = None
    material: list[str] | None = None
    fit: list[str] | None = None
    sleeve: list[str] | None = None
    neckline: list[str] | None = None
    product_features: list[str] | None = None
    style_attributes: list[str] | None = None
    min_discount_price_inr: int | None = Field(default=None, ge=0)
    max_discount_price_inr: int | None = Field(default=None, ge=0)

    @field_validator("brand", "brand_normalized", "category_gender", "product_type")
    @classmethod
    def strip_optional_scalars(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator(*sorted(QUERY_CONSTRAINT_MULTI_VALUE_FIELDS))
    @classmethod
    def validate_multivalue_fields(
        cls, value: list[str] | None, info: ValidationInfo
    ) -> list[str] | None:
        field_name = info.field_name
        assert field_name is not None
        return _validate_multivalue_field(field_name, value)

    @model_validator(mode="after")
    def validate_price_range(self) -> QueryFilterConstraints:
        min_price = self.min_discount_price_inr
        max_price = self.max_discount_price_inr
        if min_price is not None and max_price is not None and min_price > max_price:
            msg = "min_discount_price_inr must not exceed max_discount_price_inr"
            raise ValueError(msg)
        return self


class QueryLexicalIntent(BaseModel):
    """Lexical retrieval intent (future BM25 input)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    text: str = Field(min_length=1)


class QuerySemanticIntent(BaseModel):
    """Semantic retrieval intent (future embedding input)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    text: str = Field(min_length=1)


class QueryRepresentation(BaseModel):
    """Typed query-side contract for lexical, semantic, and filtering paths."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    query_text: str = Field(min_length=1)
    constraints: QueryFilterConstraints | None = None
    lexical_intent: QueryLexicalIntent
    semantic_intent: QuerySemanticIntent

    @field_validator("query_text")
    @classmethod
    def normalize_query(cls, value: str) -> str:
        return normalize_query_text(value)


def build_query_representation(
    query_text: str,
    *,
    constraints: QueryFilterConstraints | None = None,
    lexical_text: str | None = None,
    semantic_text: str | None = None,
) -> QueryRepresentation:
    """Build a query representation without query understanding or parsing."""
    normalized = normalize_query_text(query_text)
    lexical_value = normalize_query_text(lexical_text) if lexical_text is not None else normalized
    semantic_value = normalize_query_text(semantic_text) if semantic_text is not None else normalized

    if constraints is not None and constraints.category_gender is not None:
        validate_category_gender(constraints.category_gender)

    try:
        return QueryRepresentation(
            query_text=normalized,
            constraints=constraints,
            lexical_intent=QueryLexicalIntent(text=lexical_value),
            semantic_intent=QuerySemanticIntent(text=semantic_value),
        )
    except PydanticValidationError as exc:
        msg = f"invalid query representation: {exc}"
        raise QueryRepresentationError(msg) from exc


def query_representation_to_dict(representation: QueryRepresentation) -> dict[str, Any]:
    """Serialize query representation to a JSON-compatible dict."""
    return representation.model_dump(mode="json")


class QueryRepresentationBuilder:
    """Stateless builder for query representations."""

    @staticmethod
    def build(
        query_text: str,
        *,
        constraints: QueryFilterConstraints | None = None,
        lexical_text: str | None = None,
        semantic_text: str | None = None,
    ) -> QueryRepresentation:
        return build_query_representation(
            query_text,
            constraints=constraints,
            lexical_text=lexical_text,
            semantic_text=semantic_text,
        )


__all__ = [
    "QUERY_CONSTRAINT_EXCLUDED_PRODUCT_FIELDS",
    "QUERY_REPRESENTATION_FIELD_ORDER",
    "QUERY_TO_FILTERING_FACET_FIELDS",
    "QUERY_TO_FILTERING_PRICE_BOUND_FIELDS",
    "QueryFilterConstraints",
    "QueryLexicalIntent",
    "QueryRepresentation",
    "QueryRepresentationBuilder",
    "build_query_representation",
    "normalize_query_text",
    "query_representation_to_dict",
]
