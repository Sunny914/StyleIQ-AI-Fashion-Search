"""Public product API contracts (Phase 13.1).

Catalog read models are obtained through the product serving boundary in Phase 13.2.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ProductCatalogReadModel(BaseModel):
    """Infrastructure → serving read boundary (not a public HTTP response by itself)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    product_id: str = Field(min_length=1)
    brand: str | None = None
    brand_normalized: str | None = None
    description: str | None = None
    image_url: str | None = None
    product_url: str | None = None
    category_gender: str | None = None
    product_type: str | None = None


class ProductApiResponse(BaseModel):
    """GET /api/v1/products/{product_id} response."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    product_id: str = Field(min_length=1)
    brand: str | None = None
    description: str | None = None
    image_url: str | None = None
    product_url: str | None = None
    category_gender: str | None = None
    product_type: str | None = None
    request_id: str = Field(min_length=1)


__all__ = [
    "ProductApiResponse",
    "ProductCatalogReadModel",
]
