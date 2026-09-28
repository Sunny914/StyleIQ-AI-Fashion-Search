"""Diversity key extraction for recommendation selection (Phase 11.6)."""

from __future__ import annotations

from productiq.representation.filtering import FilteringRepresentation
from productiq.representation.schema import ProductRepresentation


def _normalized_scalar(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        return None
    return stripped.casefold()


def diversity_brand_key(
    *,
    filtering: FilteringRepresentation | None,
    product: ProductRepresentation | None,
) -> str | None:
    """Brand bucket for diversity; ``None`` means the brand quota does not apply."""
    if filtering is not None:
        key = _normalized_scalar(filtering.brand_normalized) or _normalized_scalar(filtering.brand)
        if key is not None:
            return key
    if product is not None:
        return _normalized_scalar(product.brand_normalized) or _normalized_scalar(product.brand)
    return None


def diversity_product_type_key(
    *,
    filtering: FilteringRepresentation | None,
    product: ProductRepresentation | None,
) -> str | None:
    """Product-type bucket for diversity; ``None`` disables type quota for this row."""
    if filtering is not None:
        key = _normalized_scalar(filtering.product_type)
        if key is not None:
            return key
    if product is not None:
        return _normalized_scalar(product.product_type)
    return None


__all__ = ["diversity_brand_key", "diversity_product_type_key"]
