"""Contract for the Phase 4.12 database vector-search primitive."""

from __future__ import annotations

import math
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from productiq.exceptions.base import SemanticRetrievalError
from productiq.retrieval.semantic import validate_semantic_retrieval_top_k
from productiq.retrieval.vector_index_schema import PRODUCTIQ_EMBEDDING_DIMENSION


class VectorDistanceMetric(StrEnum):
    """pgvector distance semantics exposed by ProductIQ (Phase 4.12: cosine only)."""

    COSINE = "cosine"


def cosine_distance_to_similarity(distance: float) -> float:
    """Convert pgvector cosine distance to cosine similarity.

    For pgvector with ``vector_cosine_ops``, ``distance = 1 - cosine_similarity``.
    """
    if not math.isfinite(distance):
        msg = "cosine distance must be finite"
        raise SemanticRetrievalError(msg)
    return 1.0 - distance


def validate_query_embedding_dimension(dimension: int) -> int:
    """Ensure a query vector matches the frozen ProductIQ embedding dimension."""
    if dimension != PRODUCTIQ_EMBEDDING_DIMENSION:
        msg = (
            f"query vector dimension must be {PRODUCTIQ_EMBEDDING_DIMENSION}, "
            f"received {dimension}"
        )
        raise SemanticRetrievalError(msg)
    return dimension


def validate_query_embedding_values(values: tuple[float, ...]) -> tuple[float, ...]:
    """Validate query vector components before issuing a database search."""
    validate_query_embedding_dimension(len(values))
    if not values:
        msg = "query vector must not be empty"
        raise SemanticRetrievalError(msg)
    norm_sq = 0.0
    for component in values:
        if not math.isfinite(component):
            msg = "query vector components must be finite"
            raise SemanticRetrievalError(msg)
        norm_sq += component * component
    if norm_sq == 0.0:
        msg = "query vector must not have zero L2 norm"
        raise SemanticRetrievalError(msg)
    return values


class VectorSearchPrimitiveRequest(BaseModel):
    """Input contract for the database-level vector search primitive (no NL query)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    query_vector: tuple[float, ...] = Field(min_length=PRODUCTIQ_EMBEDDING_DIMENSION)
    top_k: int = Field(gt=0)
    distance_metric: VectorDistanceMetric = VectorDistanceMetric.COSINE

    @field_validator("query_vector")
    @classmethod
    def validate_vector(cls, value: tuple[float, ...]) -> tuple[float, ...]:
        return validate_query_embedding_values(value)

    @field_validator("top_k")
    @classmethod
    def validate_top_k(cls, value: int) -> int:
        return validate_semantic_retrieval_top_k(value)


class VectorSearchPrimitiveHit(BaseModel):
    """One row returned by the pgvector search primitive."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    product_id: str = Field(min_length=1)
    distance: float = Field(
        description="pgvector cosine distance (lower is nearer); not BM25 or hybrid score."
    )
    similarity: float = Field(
        description="cosine similarity derived as 1 - distance for unit-norm catalog vectors."
    )

    @field_validator("product_id")
    @classmethod
    def validate_product_id(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            msg = "product_id must not be empty"
            raise ValueError(msg)
        return stripped

    @field_validator("distance", "similarity")
    @classmethod
    def validate_finite_scores(cls, value: float) -> float:
        if not math.isfinite(value):
            msg = "distance and similarity must be finite"
            raise ValueError(msg)
        return value


class VectorSearchPrimitiveResponse(BaseModel):
    """Ordered nearest-neighbor hits from PostgreSQL HNSW (deterministic tie-break by product_id)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    hits: tuple[VectorSearchPrimitiveHit, ...]
    requested_top_k: int = Field(gt=0)
    distance_metric: VectorDistanceMetric = VectorDistanceMetric.COSINE


__all__ = [
    "VectorDistanceMetric",
    "VectorSearchPrimitiveHit",
    "VectorSearchPrimitiveRequest",
    "VectorSearchPrimitiveResponse",
    "cosine_distance_to_similarity",
    "validate_query_embedding_dimension",
    "validate_query_embedding_values",
]
