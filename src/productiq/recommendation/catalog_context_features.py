"""Catalog and seed-relative context features (Phase 11.4)."""

from __future__ import annotations

from productiq.recommendation.feature_schema import CatalogContextFeatureGroup
from productiq.representation.filtering import FilteringRepresentation


def extract_catalog_context_features(
    candidate_filtering: FilteringRepresentation | None,
    *,
    seed_filtering: FilteringRepresentation | None = None,
) -> CatalogContextFeatureGroup:
    """Extract raw price fields and optional seed-relative deltas (no popularity or behavioral signals)."""
    if candidate_filtering is None:
        return CatalogContextFeatureGroup()
    discount_amount = candidate_filtering.original_price_inr - candidate_filtering.discount_price_inr
    discount_amount = max(discount_amount, 0)
    discount_delta: int | None = None
    original_delta: int | None = None
    if seed_filtering is not None:
        discount_delta = (
            candidate_filtering.discount_price_inr - seed_filtering.discount_price_inr
        )
        original_delta = (
            candidate_filtering.original_price_inr - seed_filtering.original_price_inr
        )
    return CatalogContextFeatureGroup(
        discount_price_inr=candidate_filtering.discount_price_inr,
        original_price_inr=candidate_filtering.original_price_inr,
        discount_amount_inr=discount_amount,
        discount_price_delta_from_seed_inr=discount_delta,
        original_price_delta_from_seed_inr=original_delta,
    )


__all__ = ["extract_catalog_context_features"]
