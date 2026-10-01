"""Product catalog read boundary for HTTP serving (Phase 13.5)."""

from __future__ import annotations

import math
from typing import Protocol, runtime_checkable

from productiq.serving.product_schema import ProductCatalogReadModel


@runtime_checkable
class ProductCatalogReadProvider(Protocol):
    """Framework-independent catalog lookup by product_id."""

    def get_product(self, product_id: str) -> ProductCatalogReadModel | None:
        """Return one catalog row or None when the product_id is absent."""


class InMemoryProductCatalogReadProvider:
    """Test-oriented provider backed by a pre-built index."""

    def __init__(self, records: dict[str, ProductCatalogReadModel]) -> None:
        self._records = dict(records)

    def get_product(self, product_id: str) -> ProductCatalogReadModel | None:
        return self._records.get(product_id)


def catalog_read_model_from_processed_row(row: dict[str, object]) -> ProductCatalogReadModel:
    """Map a processed-catalog row dict into the serving read model."""
    product_id = str(row["product_id"]).strip()
    return ProductCatalogReadModel(
        product_id=product_id,
        brand=_optional_str(row.get("brand")),
        brand_normalized=_optional_str(row.get("brand_normalized")),
        description=_optional_str(row.get("description")),
        image_url=_optional_str(row.get("image_url")),
        product_url=_optional_str(row.get("product_url")),
        category_gender=_optional_str(row.get("category_gender")),
        product_type=_optional_str(row.get("product_type")),
    )


def _optional_str(value: object | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    text = str(value).strip()
    return text or None


__all__ = [
    "InMemoryProductCatalogReadProvider",
    "ProductCatalogReadProvider",
    "catalog_read_model_from_processed_row",
]
