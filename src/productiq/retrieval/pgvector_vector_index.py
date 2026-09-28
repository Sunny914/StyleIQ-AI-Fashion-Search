"""PostgreSQL/pgvector ``VectorIndex`` adapter (Phase 4.13)."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.engine import Engine

from productiq.retrieval.pgvector_search import (
    search_products_by_embedding,
    semantic_hits_from_vector_search,
)
from productiq.retrieval.semantic import SemanticSearchHit, SemanticVector, VectorIndex


@dataclass(frozen=True)
class PgVectorProductVectorIndex:
    """``VectorIndex`` implementation backed by Phase 4.12 pgvector search."""

    engine: Engine

    def search(self, query_vector: SemanticVector, *, top_k: int) -> tuple[SemanticSearchHit, ...]:
        response = search_products_by_embedding(
            self.engine,
            query_vector,
            top_k=top_k,
        )
        return semantic_hits_from_vector_search(response)


def create_pgvector_product_vector_index(engine: Engine) -> PgVectorProductVectorIndex:
    """Construct a vector index adapter for the ProductIQ ``products`` HNSW index."""
    return PgVectorProductVectorIndex(engine=engine)


def pgvector_vector_index_satisfies_protocol(index: PgVectorProductVectorIndex) -> bool:
    """Return whether ``index`` implements the ``VectorIndex`` protocol."""
    return isinstance(index, VectorIndex)


__all__ = [
    "PgVectorProductVectorIndex",
    "create_pgvector_product_vector_index",
    "pgvector_vector_index_satisfies_protocol",
]
