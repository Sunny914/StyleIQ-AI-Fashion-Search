"""Candidate-ID catalog hard filtering (Phase 4.19)."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from sqlalchemy import select
from sqlalchemy.orm import Session

from productiq.database.models.product import Product
from productiq.exceptions.base import CatalogValidationError
from productiq.representation.filtering import (
    FilteringRepresentation,
    build_filtering_representation_from_canonical,
)
from productiq.representation.query_contract import QueryRepresentation
from productiq.retrieval.catalog_constraint_match import (
    constraints_are_active,
    filtering_satisfies_query_constraints,
)


@runtime_checkable
class CatalogCandidateFilter(Protocol):
    """Filter an ordered candidate ID list using query hard constraints."""

    def filter_candidate_ids(
        self,
        *,
        query: QueryRepresentation,
        candidate_product_ids: tuple[str, ...],
    ) -> tuple[str, ...]:
        """Return candidate IDs that satisfy constraints, preserving input order."""


def product_orm_to_canonical_record(product: Product) -> dict[str, object]:
    return {
        "product_id": product.product_id,
        "brand": product.brand,
        "brand_normalized": product.brand_normalized,
        "category_gender": product.category_gender,
        "product_type": product.product_type,
        "color_raw": product.color_raw,
        "color_normalized": product.color_normalized,
        "color_is_coded": product.color_is_coded,
        "pattern": product.pattern,
        "material": product.material,
        "fit": product.fit,
        "sleeve": product.sleeve,
        "neckline": product.neckline,
        "product_features": product.product_features,
        "style_attributes": product.style_attributes,
        "discount_price_inr": product.discount_price_inr,
        "original_price_inr": product.original_price_inr,
        "price_anomaly": product.price_anomaly,
        "source": product.source,
    }


def filtering_representation_from_product(product: Product) -> FilteringRepresentation:
    return build_filtering_representation_from_canonical(product_orm_to_canonical_record(product))


class InMemoryCatalogCandidateFilter:
    """Test-oriented filter backed by pre-built filtering representations."""

    def __init__(self, filtering_by_product_id: dict[str, FilteringRepresentation]) -> None:
        self._filtering_by_product_id = dict(filtering_by_product_id)

    def filter_candidate_ids(
        self,
        *,
        query: QueryRepresentation,
        candidate_product_ids: tuple[str, ...],
    ) -> tuple[str, ...]:
        constraints = query.constraints
        if constraints is None or not constraints_are_active(constraints):
            return candidate_product_ids
        kept: list[str] = []
        for product_id in candidate_product_ids:
            filtering = self._filtering_by_product_id.get(product_id)
            if filtering is None:
                msg = f"filtering metadata missing for candidate product_id {product_id!r}"
                raise CatalogValidationError(msg)
            if filtering_satisfies_query_constraints(filtering, constraints):
                kept.append(product_id)
        return tuple(kept)


class PostgresCatalogCandidateFilter:
    """PostgreSQL-backed candidate filter (batch lookup by product_id only)."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def filter_candidate_ids(
        self,
        *,
        query: QueryRepresentation,
        candidate_product_ids: tuple[str, ...],
    ) -> tuple[str, ...]:
        constraints = query.constraints
        if constraints is None or not constraints_are_active(constraints):
            return candidate_product_ids
        if not candidate_product_ids:
            return ()
        stmt = select(Product).where(Product.product_id.in_(candidate_product_ids))
        rows = list(self._session.scalars(stmt))
        by_id = {row.product_id: row for row in rows}
        kept: list[str] = []
        for product_id in candidate_product_ids:
            product = by_id.get(product_id)
            if product is None:
                msg = f"catalog row missing for candidate product_id {product_id!r}"
                raise CatalogValidationError(msg)
            filtering = filtering_representation_from_product(product)
            if filtering_satisfies_query_constraints(filtering, constraints):
                kept.append(product_id)
        return tuple(kept)


__all__ = [
    "CatalogCandidateFilter",
    "InMemoryCatalogCandidateFilter",
    "PostgresCatalogCandidateFilter",
    "filtering_representation_from_product",
    "product_orm_to_canonical_record",
]
