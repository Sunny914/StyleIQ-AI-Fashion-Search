"""Semantic retrieval foundations: vectors, similarity, and future index boundary (Phase 4.9)."""

from __future__ import annotations

import math
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

from productiq.exceptions.base import SemanticRetrievalError
from productiq.representation.query_contract import QueryRepresentation
from productiq.retrieval.contracts import (
    RetrievalCandidate,
    RetrievalMethod,
    RetrievalRequest,
    RetrievalResponse,
    RetrievalResponseMetadata,
)
from productiq.retrieval.query_for_retrieval import (
    PRODUCT_SEMANTIC_RETRIEVAL_FIELD,
    QUERY_SEMANTIC_RETRIEVAL_ATTRIBUTE,
    RetrievalQueryView,
    build_retrieval_query_view,
)


class SemanticSimilarityMetric(StrEnum):
    """Supported semantic similarity measures (Phase 4.9: cosine only)."""

    COSINE = "cosine"


class SemanticVector(BaseModel):
    """Immutable dense vector for future embedding and vector-index search."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    values: tuple[float, ...] = Field(min_length=1)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def dimension(self) -> int:
        return len(self.values)

    @field_validator("values")
    @classmethod
    def validate_finite_values(cls, value: tuple[float, ...]) -> tuple[float, ...]:
        for component in value:
            if not math.isfinite(component):
                msg = "semantic vector components must be finite numbers"
                raise ValueError(msg)
        return value

    def to_tuple(self) -> tuple[float, ...]:
        """Return vector components as a tuple (no copy semantics guarantee beyond immutability)."""
        return self.values


def semantic_vector_from_sequence(values: tuple[float, ...] | list[float]) -> SemanticVector:
    """Construct a ``SemanticVector`` from a sequence of components."""
    if not values:
        msg = "semantic vector must contain at least one component"
        raise SemanticRetrievalError(msg)
    return SemanticVector(values=tuple(float(v) for v in values))


def _vector_components(
    vector: SemanticVector | tuple[float, ...] | list[float],
) -> tuple[float, ...]:
    if isinstance(vector, SemanticVector):
        return vector.values
    return tuple(float(v) for v in vector)


def _l2_norm(components: tuple[float, ...]) -> float:
    return math.sqrt(sum(component * component for component in components))


def cosine_similarity(
    left: SemanticVector | tuple[float, ...] | list[float],
    right: SemanticVector | tuple[float, ...] | list[float],
) -> float:
    """Cosine similarity between two vectors (symmetric, deterministic).

    Raises ``SemanticRetrievalError`` when vectors are empty, dimension-mismatched,
    non-finite, or have zero L2 norm (similarity undefined).
    """
    left_components = _vector_components(left)
    right_components = _vector_components(right)
    if not left_components or not right_components:
        msg = "cosine similarity requires non-empty vectors"
        raise SemanticRetrievalError(msg)
    if len(left_components) != len(right_components):
        msg = "cosine similarity requires matching vector dimension"
        raise SemanticRetrievalError(msg)
    for component in (*left_components, *right_components):
        if not math.isfinite(component):
            msg = "cosine similarity requires finite vector components"
            raise SemanticRetrievalError(msg)
    left_norm = _l2_norm(left_components)
    right_norm = _l2_norm(right_components)
    if left_norm == 0.0 or right_norm == 0.0:
        msg = "cosine similarity is undefined for zero-norm vectors"
        raise SemanticRetrievalError(msg)
    dot = sum(left_val * right_val for left_val, right_val in zip(left_components, right_components, strict=True))
    result = dot / (left_norm * right_norm)
    if not math.isfinite(result):
        msg = "cosine similarity produced a non-finite result"
        raise SemanticRetrievalError(msg)
    return result


class SemanticRetrievalConfig(BaseModel):
    """Semantic retrieval configuration (no embedding model or vector DB settings)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    similarity_metric: SemanticSimilarityMetric = SemanticSimilarityMetric.COSINE


class SemanticSearchHit(BaseModel):
    """One vector-index search hit before mapping to ``RetrievalCandidate``."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    product_id: str = Field(min_length=1)
    similarity: float = Field(
        description="Semantic similarity score (Phase 4.9: cosine in [-1, 1]); not BM25 or final rank."
    )

    @field_validator("product_id")
    @classmethod
    def validate_product_id(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            msg = "product_id must not be empty"
            raise ValueError(msg)
        return stripped

    @field_validator("similarity")
    @classmethod
    def validate_finite_similarity(cls, value: float) -> float:
        if not math.isfinite(value):
            msg = "similarity must be a finite number"
            raise ValueError(msg)
        return value


@runtime_checkable
class VectorIndex(Protocol):
    """Future vector index boundary: query vector in, ranked hits out (no storage in Phase 4.9)."""

    def search(self, query_vector: SemanticVector, *, top_k: int) -> tuple[SemanticSearchHit, ...]: ...


def validate_semantic_retrieval_top_k(top_k: int) -> int:
    if top_k <= 0:
        msg = "semantic retrieval top_k must be positive"
        raise SemanticRetrievalError(msg)
    return top_k


def semantic_retrieval_text_from_query(query: QueryRepresentation) -> str:
    """Semantic retrieval input text aligned with product ``semantic_text``."""
    return build_retrieval_query_view(query).semantic_retrieval_text


def semantic_retrieval_text_from_request(request: RetrievalRequest) -> str:
    """Semantic retrieval input text from a Phase 4.2 ``RetrievalRequest``."""
    return semantic_retrieval_text_from_query(request.query)


def build_semantic_retrieval_query_view(query: QueryRepresentation) -> RetrievalQueryView:
    """Expose ``RetrievalQueryView`` for semantic paths (same projection as Phase 4.3)."""
    return build_retrieval_query_view(query)


def semantic_retrieval_candidate(
    product_id: str,
    *,
    similarity: float,
    metadata: dict[str, Any] | None = None,
) -> RetrievalCandidate:
    """Map a semantic similarity score to a ``RetrievalCandidate`` (``method=vector``)."""
    return RetrievalCandidate(
        product_id=product_id,
        score=similarity,
        method=RetrievalMethod.VECTOR,
        metadata=metadata,
    )


def semantic_search_hits_to_retrieval_candidates(
    hits: tuple[SemanticSearchHit, ...] | list[SemanticSearchHit],
) -> tuple[RetrievalCandidate, ...]:
    """Convert vector-index hits to retrieval candidates preserving similarity scores."""
    return tuple(
        semantic_retrieval_candidate(hit.product_id, similarity=hit.similarity) for hit in hits
    )


def semantic_hits_to_retrieval_response(
    hits: tuple[SemanticSearchHit, ...] | list[SemanticSearchHit],
    *,
    requested_top_k: int,
) -> RetrievalResponse:
    """Assemble a ``RetrievalResponse`` from semantic search hits (future vector retriever helper)."""
    top_k = validate_semantic_retrieval_top_k(requested_top_k)
    ordered = tuple(hits)[:top_k]
    return RetrievalResponse(
        candidates=semantic_search_hits_to_retrieval_candidates(ordered),
        metadata=RetrievalResponseMetadata(requested_top_k=top_k),
    )


def semantic_retrieval_alignment() -> tuple[tuple[str, str], ...]:
    """Product ↔ query semantic field alignment (Phase 3 representation contract)."""
    return ((PRODUCT_SEMANTIC_RETRIEVAL_FIELD, QUERY_SEMANTIC_RETRIEVAL_ATTRIBUTE),)


__all__ = [
    "PRODUCT_SEMANTIC_RETRIEVAL_FIELD",
    "QUERY_SEMANTIC_RETRIEVAL_ATTRIBUTE",
    "SemanticRetrievalConfig",
    "SemanticSearchHit",
    "SemanticSimilarityMetric",
    "SemanticVector",
    "VectorIndex",
    "build_semantic_retrieval_query_view",
    "cosine_similarity",
    "semantic_hits_to_retrieval_response",
    "semantic_retrieval_alignment",
    "semantic_retrieval_candidate",
    "semantic_retrieval_text_from_query",
    "semantic_retrieval_text_from_request",
    "semantic_search_hits_to_retrieval_candidates",
    "semantic_vector_from_sequence",
    "validate_semantic_retrieval_top_k",
]
