"""Validation and Phase 2 multi-value parsing for product representation."""

from __future__ import annotations

import math
from typing import Any

from productiq.exceptions.base import ProductRepresentationError
from productiq.representation.ontology import CATEGORY_GENDER_VALUES, MULTI_VALUE_DELIMITER
from productiq.representation.schema import ProductRepresentation


def is_missing_value(value: Any) -> bool:
    """Return True for None or floating NaN (e.g. from Parquet/pandas)."""
    if value is None:
        return True
    return isinstance(value, float) and math.isnan(value)


def parse_pipe_delimited_multivalue(raw: Any) -> list[str] | None:
    """Convert Phase 2 pipe-delimited storage into an ordered, deduplicated list."""
    if is_missing_value(raw):
        return None
    if not isinstance(raw, str):
        msg = f"expected string or null for multi-value field, got {type(raw).__name__}"
        raise ProductRepresentationError(msg)
    if raw.strip() == "":
        return None

    tokens: list[str] = []
    seen: set[str] = set()
    for part in raw.split(MULTI_VALUE_DELIMITER):
        token = part.strip()
        if not token:
            continue
        if token in seen:
            continue
        seen.add(token)
        tokens.append(token)

    if not tokens:
        return None
    return tokens


def optional_scalar_string(raw: Any) -> str | None:
    """Map nullable Phase 2 scalar strings to representation scalars."""
    if is_missing_value(raw):
        return None
    if not isinstance(raw, str):
        msg = f"expected string or null for scalar field, got {type(raw).__name__}"
        raise ProductRepresentationError(msg)
    stripped = raw.strip()
    if stripped == "":
        return None
    return stripped


def required_scalar_string(raw: Any, field_name: str) -> str:
    """Map required Phase 2 scalar strings."""
    if is_missing_value(raw):
        msg = f"{field_name} is required"
        raise ProductRepresentationError(msg)
    if not isinstance(raw, str):
        msg = f"{field_name} must be a string"
        raise ProductRepresentationError(msg)
    stripped = raw.strip()
    if not stripped:
        msg = f"{field_name} must not be empty"
        raise ProductRepresentationError(msg)
    return stripped


def is_valid_category_gender(value: str) -> bool:
    return value.strip().lower() in CATEGORY_GENDER_VALUES


def validate_category_gender(value: str) -> None:
    if not is_valid_category_gender(value):
        msg = f"invalid category_gender: {value!r}"
        raise ProductRepresentationError(msg)


def validate_product_representation(representation: ProductRepresentation) -> None:
    """Validate representation contract beyond Pydantic model construction."""
    validate_category_gender(representation.category_gender)


__all__ = [
    "is_missing_value",
    "is_valid_category_gender",
    "optional_scalar_string",
    "parse_pipe_delimited_multivalue",
    "required_scalar_string",
    "validate_category_gender",
    "validate_product_representation",
]
