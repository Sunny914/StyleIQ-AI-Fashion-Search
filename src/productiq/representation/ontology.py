"""Phase 3.2 ontology constants reused by structured product representation."""

from __future__ import annotations

# Must match `data.attributes.schema.MULTI_VALUE_DELIMITER` (Phase 2 storage contract).
MULTI_VALUE_DELIMITER = "|"

# Catalog gender values (Phase 3.2); compared case-insensitively at validation time.
CATEGORY_GENDER_VALUES: frozenset[str] = frozenset({"men", "women"})

# Representation fields stored as pipe-delimited strings in Phase 2.
MULTI_VALUE_REPRESENTATION_FIELDS: frozenset[str] = frozenset(
    {
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

__all__ = [
    "CATEGORY_GENDER_VALUES",
    "MULTI_VALUE_DELIMITER",
    "MULTI_VALUE_REPRESENTATION_FIELDS",
]
