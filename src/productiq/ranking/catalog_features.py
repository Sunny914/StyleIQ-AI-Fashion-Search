"""Catalog feature projection (Phase 10.2)."""

from __future__ import annotations

from productiq.ranking.feature_schema import CatalogFeatureGroup
from productiq.representation.filtering import FilteringRepresentation


def extract_catalog_features(
    filtering: FilteringRepresentation | None,
) -> CatalogFeatureGroup:
    """Extract raw price fields from injected filtering metadata (no database access)."""
    if filtering is None:
        return CatalogFeatureGroup()
    discount_amount = filtering.original_price_inr - filtering.discount_price_inr
    discount_amount = max(discount_amount, 0)
    return CatalogFeatureGroup(
        discount_price_inr=filtering.discount_price_inr,
        original_price_inr=filtering.original_price_inr,
        discount_amount_inr=discount_amount,
    )


__all__ = ["extract_catalog_features"]
