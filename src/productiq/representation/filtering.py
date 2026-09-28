"""Metadata and filtering representation (Phase 3.7)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator
from pydantic import ValidationError as PydanticValidationError

from productiq.exceptions.base import FilteringRepresentationError
from productiq.representation.builder import build_product_representation
from productiq.representation.ontology import MULTI_VALUE_REPRESENTATION_FIELDS
from productiq.representation.schema import ProductRepresentation, _validate_multivalue_field
from productiq.representation.validators import (
    is_missing_value,
    required_scalar_string,
    validate_category_gender,
)

FILTERING_MULTI_VALUE_FIELDS: frozenset[str] = MULTI_VALUE_REPRESENTATION_FIELDS

FILTERING_REPRESENTATION_FIELD_ORDER: tuple[str, ...] = (
    "product_id",
    "source",
    "brand",
    "brand_normalized",
    "category_gender",
    "product_type",
    "color_raw",
    "color_is_coded",
    "color",
    "pattern",
    "material",
    "fit",
    "sleeve",
    "neckline",
    "product_features",
    "style_attributes",
    "discount_price_inr",
    "original_price_inr",
    "price_anomaly",
)


class FilteringRepresentation(BaseModel):
    """Typed product-side metadata for future hard filtering (not query parsing)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    product_id: str = Field(min_length=1)
    source: str = Field(min_length=1)
    brand: str | None = None
    brand_normalized: str | None = None
    category_gender: str = Field(min_length=1)
    product_type: str | None = None
    color_raw: str = Field(min_length=1)
    color_is_coded: bool
    color: list[str] | None = None
    pattern: list[str] | None = None
    material: list[str] | None = None
    fit: list[str] | None = None
    sleeve: list[str] | None = None
    neckline: list[str] | None = None
    product_features: list[str] | None = None
    style_attributes: list[str] | None = None
    discount_price_inr: int = Field(ge=0)
    original_price_inr: int = Field(ge=0)
    price_anomaly: bool

    @field_validator("product_id", "source", "category_gender", "color_raw")
    @classmethod
    def strip_required_scalars(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            msg = "value must not be empty"
            raise ValueError(msg)
        return stripped

    @field_validator(*sorted(FILTERING_MULTI_VALUE_FIELDS))
    @classmethod
    def validate_multivalue_fields(
        cls, value: list[str] | None, info: ValidationInfo
    ) -> list[str] | None:
        field_name = info.field_name
        assert field_name is not None
        return _validate_multivalue_field(field_name, value)


def _required_bool(raw: Any, field_name: str) -> bool:
    if is_missing_value(raw):
        msg = f"{field_name} is required"
        raise FilteringRepresentationError(msg)
    if isinstance(raw, bool):
        return raw
    msg = f"{field_name} must be a boolean"
    raise FilteringRepresentationError(msg)


def _required_int(raw: Any, field_name: str) -> int:
    if is_missing_value(raw):
        msg = f"{field_name} is required"
        raise FilteringRepresentationError(msg)
    if isinstance(raw, bool):
        msg = f"{field_name} must be an integer"
        raise FilteringRepresentationError(msg)
    if isinstance(raw, int):
        return raw
    if isinstance(raw, float) and raw.is_integer():
        return int(raw)
    msg = f"{field_name} must be an integer"
    raise FilteringRepresentationError(msg)


def build_filtering_representation(
    representation: ProductRepresentation,
    *,
    source: str,
    color_raw: str,
    color_is_coded: bool,
    discount_price_inr: int,
    original_price_inr: int,
    price_anomaly: bool,
) -> FilteringRepresentation:
    """Combine structured product attributes with commercial/provenance metadata."""
    try:
        filtering = FilteringRepresentation(
            product_id=representation.product_id,
            source=source.strip(),
            brand=representation.brand,
            brand_normalized=representation.brand_normalized,
            category_gender=representation.category_gender,
            product_type=representation.product_type,
            color_raw=color_raw.strip(),
            color_is_coded=color_is_coded,
            color=representation.color,
            pattern=representation.pattern,
            material=representation.material,
            fit=representation.fit,
            sleeve=representation.sleeve,
            neckline=representation.neckline,
            product_features=representation.product_features,
            style_attributes=representation.style_attributes,
            discount_price_inr=discount_price_inr,
            original_price_inr=original_price_inr,
            price_anomaly=price_anomaly,
        )
    except PydanticValidationError as exc:
        msg = f"invalid filtering representation: {exc}"
        raise FilteringRepresentationError(msg) from exc

    validate_category_gender(filtering.category_gender)
    return filtering


def build_filtering_representation_from_canonical(
    record: Mapping[str, Any],
) -> FilteringRepresentation:
    """Build filtering representation from a Phase 2 canonical catalog record."""
    representation = build_product_representation(record)
    return build_filtering_representation(
        representation,
        source=required_scalar_string(record.get("source"), "source"),
        color_raw=required_scalar_string(record.get("color_raw"), "color_raw"),
        color_is_coded=_required_bool(record.get("color_is_coded"), "color_is_coded"),
        discount_price_inr=_required_int(record.get("discount_price_inr"), "discount_price_inr"),
        original_price_inr=_required_int(record.get("original_price_inr"), "original_price_inr"),
        price_anomaly=_required_bool(record.get("price_anomaly"), "price_anomaly"),
    )


def filtering_representation_to_dict(
    representation: FilteringRepresentation,
) -> dict[str, Any]:
    """Return JSON-compatible dict with stable field order."""
    data = representation.model_dump(mode="json")
    return {key: data[key] for key in FILTERING_REPRESENTATION_FIELD_ORDER}


class FilteringRepresentationBuilder:
    """Stateless builder for filtering representations."""

    @staticmethod
    def from_canonical(record: Mapping[str, Any]) -> FilteringRepresentation:
        return build_filtering_representation_from_canonical(record)

    @staticmethod
    def build(
        representation: ProductRepresentation,
        *,
        source: str,
        color_raw: str,
        color_is_coded: bool,
        discount_price_inr: int,
        original_price_inr: int,
        price_anomaly: bool,
    ) -> FilteringRepresentation:
        return build_filtering_representation(
            representation,
            source=source,
            color_raw=color_raw,
            color_is_coded=color_is_coded,
            discount_price_inr=discount_price_inr,
            original_price_inr=original_price_inr,
            price_anomaly=price_anomaly,
        )


__all__ = [
    "FILTERING_REPRESENTATION_FIELD_ORDER",
    "FilteringRepresentation",
    "FilteringRepresentationBuilder",
    "build_filtering_representation",
    "build_filtering_representation_from_canonical",
    "filtering_representation_to_dict",
]
