"""Processed ProductIQ dataset schema and contract constants."""

from __future__ import annotations

from data.attributes.schema import ATTRIBUTE_COLUMN_ORDER, ATTRIBUTE_STRING_DTYPE
from data.catalog.schema import (
    AJIO_SOURCE_NAME,
    CANONICAL_BOOLEAN_DTYPE,
    CANONICAL_COLUMN_ORDER,
    CANONICAL_NULLABLE_INT_DTYPE,
    CANONICAL_STRING_DTYPE,
)

# Bump when processed column names, dtypes, or semantic contract change.
PROCESSED_DATASET_SCHEMA_VERSION = "1.0.0"

PROCESSED_DATASET_NAME = "product_catalog"
PROCESSED_DATASET_FORMAT = "parquet"
PROCESSED_PARQUET_FILENAME = "product_catalog.parquet"
PROCESSED_MANIFEST_FILENAME = "product_catalog.manifest.json"
CHECKSUM_ALGORITHM = "sha256"
PIPELINE_PHASE = "2.9"

PROCESSED_COLUMN_ORDER: tuple[str, ...] = CANONICAL_COLUMN_ORDER + ATTRIBUTE_COLUMN_ORDER
PROCESSED_COLUMN_COUNT = len(PROCESSED_COLUMN_ORDER)

AJIO_PROCESSED_ROW_COUNT = 367_172

CANONICAL_STRING_COLUMNS: tuple[str, ...] = tuple(
    column
    for column in CANONICAL_COLUMN_ORDER
    if column
    not in (
        "color_is_coded",
        "price_anomaly",
        "discount_price_inr",
        "original_price_inr",
    )
)

ATTRIBUTE_COLUMNS: tuple[str, ...] = ATTRIBUTE_COLUMN_ORDER

PROCESSED_EXPECTED_DTYPES: dict[str, str] = {
    **{column: CANONICAL_STRING_DTYPE for column in CANONICAL_STRING_COLUMNS},
    "color_is_coded": CANONICAL_BOOLEAN_DTYPE,
    "price_anomaly": CANONICAL_BOOLEAN_DTYPE,
    "discount_price_inr": CANONICAL_NULLABLE_INT_DTYPE,
    "original_price_inr": CANONICAL_NULLABLE_INT_DTYPE,
    **{column: ATTRIBUTE_STRING_DTYPE for column in ATTRIBUTE_COLUMNS},
}

assert PROCESSED_COLUMN_COUNT == 22
assert PROCESSED_COLUMN_ORDER[0] == "product_id"
assert PROCESSED_COLUMN_ORDER[-1] == "style_attributes"

__all__ = [
    "AJIO_PROCESSED_ROW_COUNT",
    "AJIO_SOURCE_NAME",
    "ATTRIBUTE_COLUMNS",
    "CANONICAL_STRING_COLUMNS",
    "CHECKSUM_ALGORITHM",
    "PIPELINE_PHASE",
    "PROCESSED_COLUMN_COUNT",
    "PROCESSED_COLUMN_ORDER",
    "PROCESSED_DATASET_FORMAT",
    "PROCESSED_DATASET_NAME",
    "PROCESSED_DATASET_SCHEMA_VERSION",
    "PROCESSED_EXPECTED_DTYPES",
    "PROCESSED_MANIFEST_FILENAME",
    "PROCESSED_PARQUET_FILENAME",
]
