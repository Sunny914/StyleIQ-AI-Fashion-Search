"""Seed product resolution for recommendation candidate generation (Phase 11.2)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Protocol, runtime_checkable

from sqlalchemy import select
from sqlalchemy.orm import Session

from productiq.database.models.product import Product
from productiq.exceptions.base import CatalogValidationError
from productiq.representation.builder import build_product_representation
from productiq.representation.schema import ProductRepresentation
from productiq.retrieval.catalog_candidate_filter import product_orm_to_canonical_record


@runtime_checkable
class SeedProductResolver(Protocol):
    """Resolve a seed ``ProductRepresentation`` or fail explicitly."""

    def resolve_seed_product(self, seed_product_id: str) -> ProductRepresentation:
        """Return the seed product; raise when the catalog row is missing."""


class InMemorySeedProductResolver:
    """Test-oriented resolver backed by pre-built product representations."""

    def __init__(self, products_by_id: Mapping[str, ProductRepresentation]) -> None:
        self._products_by_id = dict(products_by_id)

    def resolve_seed_product(self, seed_product_id: str) -> ProductRepresentation:
        product = self._products_by_id.get(seed_product_id)
        if product is None:
            msg = f"catalog row missing for seed product_id {seed_product_id!r}"
            raise CatalogValidationError(msg)
        return product


class PostgresSeedProductResolver:
    """PostgreSQL-backed seed lookup using existing catalog ORM models."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def resolve_seed_product(self, seed_product_id: str) -> ProductRepresentation:
        stmt = select(Product).where(Product.product_id == seed_product_id)
        row = self._session.scalar(stmt)
        if row is None:
            msg = f"catalog row missing for seed product_id {seed_product_id!r}"
            raise CatalogValidationError(msg)
        canonical = product_orm_to_canonical_record(row)
        return build_product_representation(canonical)


@runtime_checkable
class RecommendationCatalogAccess(Protocol):
    """Read-only catalog access for attribute generation and constraint filtering."""

    def resolve_seed_product(self, seed_product_id: str) -> ProductRepresentation:
        """Return the seed representation."""

    def list_catalog_products(self) -> tuple[ProductRepresentation, ...]:
        """Return all catalog products for deterministic attribute generation."""


class InMemoryRecommendationCatalog:
    """In-memory catalog snapshot for tests and offline orchestration."""

    def __init__(
        self,
        products: Sequence[ProductRepresentation],
    ) -> None:
        self._products_by_id = {product.product_id: product for product in products}

    def resolve_seed_product(self, seed_product_id: str) -> ProductRepresentation:
        product = self._products_by_id.get(seed_product_id)
        if product is None:
            msg = f"catalog row missing for seed product_id {seed_product_id!r}"
            raise CatalogValidationError(msg)
        return product

    def list_catalog_products(self) -> tuple[ProductRepresentation, ...]:
        return tuple(self._products_by_id[product_id] for product_id in sorted(self._products_by_id))


class PostgresRecommendationCatalog:
    """PostgreSQL-backed catalog listing for attribute generation."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def resolve_seed_product(self, seed_product_id: str) -> ProductRepresentation:
        return PostgresSeedProductResolver(self._session).resolve_seed_product(seed_product_id)

    def list_catalog_products(self) -> tuple[ProductRepresentation, ...]:
        rows = list(self._session.scalars(select(Product)))
        built: list[ProductRepresentation] = []
        for row in sorted(rows, key=lambda item: item.product_id):
            built.append(build_product_representation(product_orm_to_canonical_record(row)))
        return tuple(built)


__all__ = [
    "InMemoryRecommendationCatalog",
    "InMemorySeedProductResolver",
    "PostgresRecommendationCatalog",
    "PostgresSeedProductResolver",
    "RecommendationCatalogAccess",
    "SeedProductResolver",
]
