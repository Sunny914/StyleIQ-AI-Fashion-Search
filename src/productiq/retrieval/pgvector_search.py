"""PostgreSQL/pgvector nearest-neighbor search primitive (Phase 4.12)."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import cast

from sqlalchemy import text
from sqlalchemy.engine import Engine

from productiq.database.catalog_contract import PRODUCT_EMBEDDING_COLUMN, PRODUCTS_TABLE_NAME
from productiq.exceptions.base import SemanticRetrievalError
from productiq.retrieval.semantic import (
    SemanticSearchHit,
    SemanticVector,
    validate_semantic_retrieval_top_k,
)
from productiq.retrieval.vector_index_contract import (
    VectorDistanceMetric,
    VectorSearchPrimitiveHit,
    VectorSearchPrimitiveResponse,
    cosine_distance_to_similarity,
    validate_query_embedding_values,
)
from productiq.retrieval.vector_index_schema import PGVECTOR_OPERATOR_CLASS

_SEARCH_SQL = text(
    f"""
    SELECT
        product_id,
        ({PRODUCT_EMBEDDING_COLUMN} <=> CAST(:query_vector AS vector)) AS distance
    FROM {PRODUCTS_TABLE_NAME}
    WHERE {PRODUCT_EMBEDDING_COLUMN} IS NOT NULL
    ORDER BY {PRODUCT_EMBEDDING_COLUMN} <=> CAST(:query_vector AS vector),
             product_id ASC
    LIMIT :top_k
    """
)


def _vector_literal(values: tuple[float, ...]) -> str:
    components = ",".join(f"{float(component):.8g}" for component in values)
    return f"[{components}]"


def search_products_by_embedding(
    engine: Engine,
    query_vector: tuple[float, ...] | SemanticVector,
    *,
    top_k: int,
    ef_search: int | None = None,
) -> VectorSearchPrimitiveResponse:
    """Run cosine-distance nearest-neighbor search against the HNSW index."""
    top_k = validate_semantic_retrieval_top_k(top_k)
    if isinstance(query_vector, SemanticVector):
        values = query_vector.values
    else:
        values = validate_query_embedding_values(tuple(float(v) for v in query_vector))

    if ef_search is not None and ef_search <= 0:
        msg = "ef_search must be positive when provided"
        raise SemanticRetrievalError(msg)

    literal = _vector_literal(values)
    params: dict[str, object] = {"query_vector": literal, "top_k": top_k}
    resolved_ef_search = max(top_k, ef_search if ef_search is not None else top_k)

    with engine.connect() as connection:
        connection.execute(text(f"SET hnsw.ef_search = {int(resolved_ef_search)}"))
        rows = connection.execute(_SEARCH_SQL, params).all()

    hits: list[VectorSearchPrimitiveHit] = []
    for product_id, distance_raw in rows:
        distance = cast(float, distance_raw)
        similarity = cosine_distance_to_similarity(distance)
        hits.append(
            VectorSearchPrimitiveHit(
                product_id=str(product_id),
                distance=distance,
                similarity=similarity,
            )
        )

    return VectorSearchPrimitiveResponse(
        hits=tuple(hits),
        requested_top_k=top_k,
        distance_metric=VectorDistanceMetric.COSINE,
    )


def semantic_hits_from_vector_search(
    response: VectorSearchPrimitiveResponse,
) -> tuple[SemanticSearchHit, ...]:
    """Map primitive hits to ``SemanticSearchHit`` for Phase 4.13 adapters."""
    return tuple(
        SemanticSearchHit(product_id=hit.product_id, similarity=hit.similarity)
        for hit in response.hits
    )


@dataclass(frozen=True)
class VectorSearchTimingSample:
    top_k: int
    duration_seconds: float
    hit_count: int


def benchmark_vector_search(
    engine: Engine,
    query_vector: tuple[float, ...],
    *,
    top_k_values: tuple[int, ...] = (10, 50),
) -> tuple[VectorSearchTimingSample, ...]:
    """Record lightweight query latency samples (not a production SLA)."""
    samples: list[VectorSearchTimingSample] = []
    for top_k in top_k_values:
        started = time.perf_counter()
        response = search_products_by_embedding(engine, query_vector, top_k=top_k)
        duration = time.perf_counter() - started
        samples.append(
            VectorSearchTimingSample(
                top_k=top_k,
                duration_seconds=duration,
                hit_count=len(response.hits),
            )
        )
    return tuple(samples)


def pgvector_operator_class_name() -> str:
    """Expose configured pgvector operator class for validation tests."""
    return PGVECTOR_OPERATOR_CLASS


__all__ = [
    "VectorSearchTimingSample",
    "benchmark_vector_search",
    "pgvector_operator_class_name",
    "search_products_by_embedding",
    "semantic_hits_from_vector_search",
]
