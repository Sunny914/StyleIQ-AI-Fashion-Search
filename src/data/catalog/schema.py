"""ProductIQ canonical product schema definitions."""

from __future__ import annotations

from dataclasses import dataclass

AJIO_SOURCE_NAME = "ajio"

CANONICAL_COLUMN_ORDER: tuple[str, ...] = (
    "product_id",
    "product_url",
    "brand",
    "brand_normalized",
    "description",
    "image_url",
    "category_gender",
    "color_raw",
    "color_normalized",
    "color_is_coded",
    "discount_price_inr",
    "original_price_inr",
    "price_anomaly",
    "source",
)

CANONICAL_STRING_DTYPE = "string"
CANONICAL_NULLABLE_INT_DTYPE = "Int64"
CANONICAL_BOOLEAN_DTYPE = "boolean"


@dataclass(frozen=True)
class CanonicalFieldDefinition:
    """Definition of one canonical product field."""

    canonical_name: str
    source_column: str | None
    dtype: str
    required: bool = True


CANONICAL_FIELD_DEFINITIONS: tuple[CanonicalFieldDefinition, ...] = (
    CanonicalFieldDefinition("product_id", "Id_Product", CANONICAL_STRING_DTYPE),
    CanonicalFieldDefinition("product_url", "Product_URL", CANONICAL_STRING_DTYPE),
    CanonicalFieldDefinition("brand", "Brand", CANONICAL_STRING_DTYPE),
    CanonicalFieldDefinition("brand_normalized", "Brand_Normalized", CANONICAL_STRING_DTYPE),
    CanonicalFieldDefinition("description", "Description", CANONICAL_STRING_DTYPE),
    CanonicalFieldDefinition("image_url", "URL_image", CANONICAL_STRING_DTYPE),
    CanonicalFieldDefinition("category_gender", "Category_by_gender", CANONICAL_STRING_DTYPE),
    CanonicalFieldDefinition("color_raw", "Color", CANONICAL_STRING_DTYPE),
    CanonicalFieldDefinition("color_normalized", "Color_Normalized", CANONICAL_STRING_DTYPE),
    CanonicalFieldDefinition("color_is_coded", "Color_Is_Coded", CANONICAL_BOOLEAN_DTYPE),
    CanonicalFieldDefinition(
        "discount_price_inr",
        "Discount Price (in Rs.)",
        CANONICAL_NULLABLE_INT_DTYPE,
    ),
    CanonicalFieldDefinition(
        "original_price_inr",
        "Original Price (in Rs.)",
        CANONICAL_NULLABLE_INT_DTYPE,
    ),
    CanonicalFieldDefinition("price_anomaly", "price_anomaly", CANONICAL_BOOLEAN_DTYPE),
    CanonicalFieldDefinition("source", None, CANONICAL_STRING_DTYPE),
)

REQUIRED_SOURCE_COLUMNS: tuple[str, ...] = tuple(
    field.source_column
    for field in CANONICAL_FIELD_DEFINITIONS
    if field.source_column is not None
)

CANONICAL_COLUMN_COUNT = len(CANONICAL_COLUMN_ORDER)

assert CANONICAL_COLUMN_COUNT == len(CANONICAL_FIELD_DEFINITIONS)
assert tuple(field.canonical_name for field in CANONICAL_FIELD_DEFINITIONS) == CANONICAL_COLUMN_ORDER
