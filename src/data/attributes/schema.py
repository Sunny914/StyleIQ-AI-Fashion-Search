"""Product attribute schema definitions."""

from __future__ import annotations

from dataclasses import dataclass

from data.catalog.schema import CANONICAL_COLUMN_ORDER

MULTI_VALUE_DELIMITER = "|"
ATTRIBUTE_TEXT_COLUMN = "description"

ATTRIBUTE_STRING_DTYPE = "string"


@dataclass(frozen=True)
class AttributeDefinition:
    """Definition of one engineered product attribute column."""

    name: str
    multi_valued: bool
    dtype: str = ATTRIBUTE_STRING_DTYPE


ATTRIBUTE_DEFINITIONS: tuple[AttributeDefinition, ...] = (
    AttributeDefinition("product_type", multi_valued=False),
    AttributeDefinition("fit", multi_valued=False),
    AttributeDefinition("pattern", multi_valued=True),
    AttributeDefinition("sleeve", multi_valued=False),
    AttributeDefinition("neckline", multi_valued=False),
    AttributeDefinition("material", multi_valued=True),
    AttributeDefinition("product_features", multi_valued=True),
    AttributeDefinition("style_attributes", multi_valued=True),
)

ATTRIBUTE_COLUMN_ORDER: tuple[str, ...] = tuple(
    attribute.name for attribute in ATTRIBUTE_DEFINITIONS
)

REQUIRED_CANONICAL_COLUMNS: tuple[str, ...] = CANONICAL_COLUMN_ORDER
