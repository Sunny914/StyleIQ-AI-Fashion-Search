"""Structured product representation schema."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

from productiq.representation.ontology import MULTI_VALUE_REPRESENTATION_FIELDS


def _validate_multivalue_field(name: str, value: list[str] | None) -> list[str] | None:
    if value is None:
        return None
    if not value:
        msg = f"{name} must not be an empty list; use null when unavailable"
        raise ValueError(msg)
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str):
            msg = f"{name} entries must be strings"
            raise TypeError(msg)
        if item == "":
            msg = f"{name} must not contain empty strings"
            raise ValueError(msg)
        if item in seen:
            msg = f"{name} must not contain duplicate values"
            raise ValueError(msg)
        seen.add(item)
    return value


class ProductRepresentation(BaseModel):
    """Application-level structured product view for downstream search and AI components."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    product_id: str = Field(min_length=1)
    brand: str | None = None
    brand_normalized: str | None = None
    category_gender: str = Field(min_length=1)
    product_type: str | None = None
    color: list[str] | None = None
    pattern: list[str] | None = None
    material: list[str] | None = None
    fit: list[str] | None = None
    sleeve: list[str] | None = None
    neckline: list[str] | None = None
    product_features: list[str] | None = None
    style_attributes: list[str] | None = None

    @field_validator("product_id", "category_gender")
    @classmethod
    def strip_required_scalars(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            msg = "value must not be empty"
            raise ValueError(msg)
        return stripped

    @field_validator(*sorted(MULTI_VALUE_REPRESENTATION_FIELDS))
    @classmethod
    def validate_multivalue_fields(
        cls, value: list[str] | None, info: ValidationInfo
    ) -> list[str] | None:
        field_name = info.field_name
        assert field_name is not None
        return _validate_multivalue_field(field_name, value)


__all__ = ["ProductRepresentation"]
