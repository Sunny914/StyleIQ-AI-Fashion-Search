"""Serialization helpers for ProductRepresentation."""

from __future__ import annotations

import json
from typing import Any

from productiq.representation.schema import ProductRepresentation

REPRESENTATION_FIELD_ORDER: tuple[str, ...] = (
    "product_id",
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
)


def representation_to_dict(representation: ProductRepresentation) -> dict[str, Any]:
    """Return a JSON-compatible dict with stable field names and ordering."""
    data = representation.model_dump(mode="json")
    return {key: data[key] for key in REPRESENTATION_FIELD_ORDER}


def representation_to_json(
    representation: ProductRepresentation,
    *,
    indent: int | None = None,
) -> str:
    """Serialize to deterministic JSON (sorted keys within nested structures)."""
    return json.dumps(
        representation_to_dict(representation),
        ensure_ascii=False,
        sort_keys=True,
        indent=indent,
    )


__all__ = [
    "REPRESENTATION_FIELD_ORDER",
    "representation_to_dict",
    "representation_to_json",
]
