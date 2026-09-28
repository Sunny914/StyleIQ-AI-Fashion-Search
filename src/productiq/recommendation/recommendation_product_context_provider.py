"""Batch candidate context loading for the recommendation pipeline (Phase 11.8)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol, runtime_checkable

from sqlalchemy import select
from sqlalchemy.orm import Session

from productiq.database.models.product import Product
from productiq.exceptions.base import CatalogValidationError, RecommendationError
from productiq.recommendation.product_context import RecommendationProductContext
from productiq.representation.builder import build_product_representation
from productiq.representation.filtering import FilteringRepresentation
from productiq.representation.schema import ProductRepresentation
from productiq.retrieval.catalog_candidate_filter import (
    filtering_representation_from_product,
    product_orm_to_canonical_record,
)


@runtime_checkable
class RecommendationProductContextProvider(Protocol):
    """Load candidate product representations and feature contexts in batch."""

    def load_candidate_context(
        self,
        *,
        product_ids: tuple[str, ...],
    ) -> tuple[
        Mapping[str, ProductRepresentation],
        Mapping[str, RecommendationProductContext],
    ]:
        """Return aligned product and context maps for the requested IDs (single batch)."""


class InMemoryRecommendationProductContextProvider:
    """Test-oriented provider backed by pre-built catalog and filtering maps."""

    def __init__(
        self,
        *,
        products_by_id: Mapping[str, ProductRepresentation],
        filtering_by_product_id: Mapping[str, FilteringRepresentation],
    ) -> None:
        self._products_by_id = dict(products_by_id)
        self._filtering_by_product_id = dict(filtering_by_product_id)
        self.load_call_count = 0
        self.last_requested_ids: tuple[str, ...] = ()

    def load_candidate_context(
        self,
        *,
        product_ids: tuple[str, ...],
    ) -> tuple[
        Mapping[str, ProductRepresentation],
        Mapping[str, RecommendationProductContext],
    ]:
        self.load_call_count += 1
        self.last_requested_ids = product_ids
        products: dict[str, ProductRepresentation] = {}
        contexts: dict[str, RecommendationProductContext] = {}
        for product_id in product_ids:
            product = self._products_by_id.get(product_id)
            if product is None:
                msg = f"catalog row missing for candidate product_id {product_id!r}"
                raise CatalogValidationError(msg)
            filtering = self._filtering_by_product_id.get(product_id)
            products[product_id] = product
            contexts[product_id] = RecommendationProductContext(
                product_id=product_id,
                filtering=filtering,
            )
        return products, contexts


class PostgresRecommendationProductContextProvider:
    """PostgreSQL-backed batch lookup for recommendation pipeline stages."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def load_candidate_context(
        self,
        *,
        product_ids: tuple[str, ...],
    ) -> tuple[
        Mapping[str, ProductRepresentation],
        Mapping[str, RecommendationProductContext],
    ]:
        if not product_ids:
            return {}, {}
        stmt = select(Product).where(Product.product_id.in_(product_ids))
        rows = list(self._session.scalars(stmt))
        by_id = {row.product_id: row for row in rows}
        products: dict[str, ProductRepresentation] = {}
        contexts: dict[str, RecommendationProductContext] = {}
        for product_id in product_ids:
            product_row = by_id.get(product_id)
            if product_row is None:
                msg = f"catalog row missing for candidate product_id {product_id!r}"
                raise CatalogValidationError(msg)
            canonical = product_orm_to_canonical_record(product_row)
            product = build_product_representation(canonical)
            filtering = filtering_representation_from_product(product_row)
            products[product_id] = product
            contexts[product_id] = RecommendationProductContext(
                product_id=product_id,
                filtering=filtering,
            )
        return products, contexts


def build_filtering_map_for_catalog_products(
    *,
    products: Mapping[str, ProductRepresentation],
    filtering_by_product_id: Mapping[str, FilteringRepresentation],
) -> dict[str, FilteringRepresentation]:
    """Resolve filtering rows required for candidate generation (deterministic)."""
    missing = [
        product_id
        for product_id in sorted(products)
        if product_id not in filtering_by_product_id
    ]
    if missing:
        msg = f"filtering metadata missing for product_ids: {missing[:5]}"
        raise RecommendationError(msg)
    return {product_id: filtering_by_product_id[product_id] for product_id in sorted(products)}


__all__ = [
    "InMemoryRecommendationProductContextProvider",
    "PostgresRecommendationProductContextProvider",
    "RecommendationProductContextProvider",
    "build_filtering_map_for_catalog_products",
]
