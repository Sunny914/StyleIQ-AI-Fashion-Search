"""Load seed product embeddings from PostgreSQL (Phase 11.2)."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.engine import Engine

from productiq.database.catalog_contract import PRODUCT_EMBEDDING_COLUMN, PRODUCTS_TABLE_NAME
from productiq.exceptions.base import CatalogValidationError, SemanticRetrievalError
from productiq.retrieval.embedding_schema import PRODUCTIQ_EMBEDDING_DIMENSION
from productiq.retrieval.semantic import SemanticVector
from productiq.retrieval.vector_index_contract import validate_query_embedding_values

_LOAD_SQL = text(
    f"""
    SELECT {PRODUCT_EMBEDDING_COLUMN}::text
    FROM {PRODUCTS_TABLE_NAME}
    WHERE product_id = :product_id
      AND {PRODUCT_EMBEDDING_COLUMN} IS NOT NULL
    """
)


def _parse_pgvector_literal(raw: str) -> tuple[float, ...]:
    stripped = raw.strip()
    if not stripped.startswith("[") or not stripped.endswith("]"):
        msg = "embedding literal must be a pgvector bracket list"
        raise SemanticRetrievalError(msg)
    body = stripped[1:-1].strip()
    if not body:
        msg = "embedding must not be empty"
        raise SemanticRetrievalError(msg)
    values = tuple(float(part) for part in body.split(","))
    return validate_query_embedding_values(values)


def parse_pgvector_embedding_literal(raw: str) -> tuple[float, ...]:
    """Parse a pgvector bracket literal into validated embedding components."""
    return _parse_pgvector_literal(raw)


@dataclass(frozen=True)
class PostgresSeedEmbeddingProvider:
    """PostgreSQL-backed seed embedding lookup using the existing ``products.embedding`` column."""

    engine: Engine

    def load_seed_embedding(self, seed_product_id: str) -> SemanticVector:
        with self.engine.connect() as connection:
            row = connection.execute(_LOAD_SQL, {"product_id": seed_product_id}).first()
        if row is None:
            msg = f"embedding missing for seed product_id {seed_product_id!r}"
            raise CatalogValidationError(msg)
        values = _parse_pgvector_literal(str(row[0]))
        if len(values) != PRODUCTIQ_EMBEDDING_DIMENSION:
            msg = (
                f"embedding dimension must be {PRODUCTIQ_EMBEDDING_DIMENSION}, "
                f"found {len(values)} for seed {seed_product_id!r}"
            )
            raise SemanticRetrievalError(msg)
        return SemanticVector(values=values)


class InMemorySeedEmbeddingProvider:
    """Test-oriented embedding lookup."""

    def __init__(self, embeddings_by_product_id: dict[str, SemanticVector]) -> None:
        self._embeddings_by_product_id = dict(embeddings_by_product_id)

    def load_seed_embedding(self, seed_product_id: str) -> SemanticVector:
        embedding = self._embeddings_by_product_id.get(seed_product_id)
        if embedding is None:
            msg = f"embedding missing for seed product_id {seed_product_id!r}"
            raise CatalogValidationError(msg)
        return embedding


__all__ = [
    "InMemorySeedEmbeddingProvider",
    "PostgresSeedEmbeddingProvider",
    "parse_pgvector_embedding_literal",
]
