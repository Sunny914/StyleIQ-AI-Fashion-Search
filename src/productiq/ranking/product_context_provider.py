"""Injected product context for ranking feature extraction (Phase 10.5)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol, runtime_checkable

from sqlalchemy import select
from sqlalchemy.orm import Session

from productiq.database.models.product import Product
from productiq.exceptions.base import CatalogValidationError, RankingError
from productiq.ranking.product_context import RankingProductContext
from productiq.representation.builder import build_product_representation
from productiq.retrieval.catalog_candidate_filter import (
    filtering_representation_from_product,
    product_orm_to_canonical_record,
)


@runtime_checkable
class RankingProductContextProvider(Protocol):
    """Load ``RankingProductContext`` for candidate product IDs (no ranking logic)."""

    def load_contexts(
        self,
        *,
        product_ids: tuple[str, ...],
    ) -> Mapping[str, RankingProductContext]:
        """Return one context per requested ID; raise when a required row is missing."""


class InMemoryRankingProductContextProvider:
    """Test-oriented provider backed by a pre-built context map."""

    def __init__(self, contexts_by_product_id: Mapping[str, RankingProductContext]) -> None:
        self._contexts_by_product_id = dict(contexts_by_product_id)

    def load_contexts(
        self,
        *,
        product_ids: tuple[str, ...],
    ) -> Mapping[str, RankingProductContext]:
        loaded: dict[str, RankingProductContext] = {}
        for product_id in product_ids:
            context = self._contexts_by_product_id.get(product_id)
            if context is None:
                msg = f"missing RankingProductContext for product_id {product_id!r}"
                raise RankingError(msg)
            loaded[product_id] = context
        return loaded


class PostgresRankingProductContextProvider:
    """PostgreSQL-backed batch lookup for ranking feature extraction."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def load_contexts(
        self,
        *,
        product_ids: tuple[str, ...],
    ) -> Mapping[str, RankingProductContext]:
        if not product_ids:
            return {}
        stmt = select(Product).where(Product.product_id.in_(product_ids))
        rows = list(self._session.scalars(stmt))
        by_id = {row.product_id: row for row in rows}
        loaded: dict[str, RankingProductContext] = {}
        for product_id in product_ids:
            product_row = by_id.get(product_id)
            if product_row is None:
                msg = f"catalog row missing for candidate product_id {product_id!r}"
                raise CatalogValidationError(msg)
            canonical = product_orm_to_canonical_record(product_row)
            product = build_product_representation(canonical)
            filtering = filtering_representation_from_product(product_row)
            loaded[product_id] = RankingProductContext(
                product_id=product_id,
                product=product,
                filtering=filtering,
            )
        return loaded


__all__ = [
    "InMemoryRankingProductContextProvider",
    "PostgresRankingProductContextProvider",
    "RankingProductContextProvider",
]
