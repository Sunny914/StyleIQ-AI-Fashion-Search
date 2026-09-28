"""Build structured product representations from Phase 2 canonical catalog records."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from pydantic import ValidationError as PydanticValidationError

from productiq.exceptions.base import ProductRepresentationError
from productiq.representation.schema import ProductRepresentation
from productiq.representation.validators import (
    optional_scalar_string,
    parse_pipe_delimited_multivalue,
    required_scalar_string,
    validate_product_representation,
)

# Canonical Phase 2 column → ProductRepresentation field.
_SCALAR_FIELD_MAP: tuple[tuple[str, str], ...] = (
    ("product_id", "product_id"),
    ("brand", "brand"),
    ("brand_normalized", "brand_normalized"),
    ("category_gender", "category_gender"),
    ("product_type", "product_type"),
)

_MULTI_VALUE_SOURCE_MAP: tuple[tuple[str, str], ...] = (
    ("color_normalized", "color"),
    ("pattern", "pattern"),
    ("material", "material"),
    ("fit", "fit"),
    ("sleeve", "sleeve"),
    ("neckline", "neckline"),
    ("product_features", "product_features"),
    ("style_attributes", "style_attributes"),
)


def build_product_representation(record: Mapping[str, Any]) -> ProductRepresentation:
    """Convert one Phase 2 canonical product record into a ProductRepresentation."""
    payload: dict[str, Any] = {}

    for source_key, target_key in _SCALAR_FIELD_MAP:
        raw = record.get(source_key)
        if target_key in {"product_id", "category_gender"}:
            payload[target_key] = required_scalar_string(raw, target_key)
        else:
            payload[target_key] = optional_scalar_string(raw)

    for source_key, target_key in _MULTI_VALUE_SOURCE_MAP:
        payload[target_key] = parse_pipe_delimited_multivalue(record.get(source_key))

    try:
        representation = ProductRepresentation.model_validate(payload)
    except PydanticValidationError as exc:
        msg = f"invalid product representation: {exc}"
        raise ProductRepresentationError(msg) from exc

    validate_product_representation(representation)
    return representation


def build_product_representations(
    records: Iterable[Mapping[str, Any]],
) -> list[ProductRepresentation]:
    """Batch-build representations without mutating input records."""
    return [build_product_representation(record) for record in records]


__all__ = [
    "build_product_representation",
    "build_product_representations",
]
