"""Batch catalog embedding access for recommendation similarity (Phase 11.3)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Protocol, runtime_checkable

from sqlalchemy import bindparam, text
from sqlalchemy.engine import Engine

from productiq.database.catalog_contract import PRODUCT_EMBEDDING_COLUMN, PRODUCTS_TABLE_NAME
from productiq.exceptions.base import CatalogValidationError, SemanticRetrievalError
from productiq.recommendation.seed_embedding import (
    parse_pgvector_embedding_literal as _parse_pgvector_literal,
)
from productiq.retrieval.embedding_schema import PRODUCTIQ_EMBEDDING_DIMENSION
from productiq.retrieval.semantic import SemanticVector


@runtime_checkable
class ProductEmbeddingProvider(Protocol):
    """Batch lookup of catalog embeddings by ``product_id``."""

    def load_embeddings(
        self,
        product_ids: tuple[str, ...],
    ) -> Mapping[str, SemanticVector]:
        """Return one embedding per requested ID (raises when required rows are missing)."""


class InMemoryProductEmbeddingProvider:
    """Test-oriented embedding provider."""

    def __init__(self, embeddings_by_product_id: Mapping[str, SemanticVector]) -> None:
        self._embeddings_by_product_id = dict(embeddings_by_product_id)
        self.load_call_count = 0
        self.last_requested_ids: tuple[str, ...] = ()

    def load_embeddings(
        self,
        product_ids: tuple[str, ...],
    ) -> Mapping[str, SemanticVector]:
        self.load_call_count += 1
        self.last_requested_ids = product_ids
        loaded: dict[str, SemanticVector] = {}
        for product_id in product_ids:
            embedding = self._embeddings_by_product_id.get(product_id)
            if embedding is None:
                msg = f"embedding missing for product_id {product_id!r}"
                raise CatalogValidationError(msg)
            loaded[product_id] = embedding
        return loaded


class PostgresProductEmbeddingProvider:
    """PostgreSQL batch embedding lookup (single query per call)."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def load_embeddings(
        self,
        product_ids: tuple[str, ...],
    ) -> Mapping[str, SemanticVector]:
        if not product_ids:
            return {}
        statement = text(
            f"""
            SELECT product_id, {PRODUCT_EMBEDDING_COLUMN}::text AS embedding_literal
            FROM {PRODUCTS_TABLE_NAME}
            WHERE product_id IN :product_ids
              AND {PRODUCT_EMBEDDING_COLUMN} IS NOT NULL
            """
        ).bindparams(bindparam("product_ids", expanding=True))
        with self._engine.connect() as connection:
            rows = connection.execute(statement, {"product_ids": list(product_ids)}).all()
        by_id: dict[str, SemanticVector] = {}
        for product_id, literal in rows:
            values = _parse_pgvector_literal(str(literal))
            if len(values) != PRODUCTIQ_EMBEDDING_DIMENSION:
                msg = (
                    f"embedding dimension must be {PRODUCTIQ_EMBEDDING_DIMENSION}, "
                    f"found {len(values)} for product_id {product_id!r}"
                )
                raise SemanticRetrievalError(msg)
            by_id[str(product_id)] = SemanticVector(values=values)
        missing = [product_id for product_id in product_ids if product_id not in by_id]
        if missing:
            msg = f"embedding missing for product_id(s): {', '.join(missing)}"
            raise CatalogValidationError(msg)
        return by_id


def merge_seed_and_candidate_embedding_ids(
    seed_product_id: str,
    candidate_product_ids: Sequence[str],
) -> tuple[str, ...]:
    ordered = [seed_product_id, *candidate_product_ids]
    return tuple(dict.fromkeys(ordered))


__all__ = [
    "InMemoryProductEmbeddingProvider",
    "PostgresProductEmbeddingProvider",
    "ProductEmbeddingProvider",
    "merge_seed_and_candidate_embedding_ids",
]
