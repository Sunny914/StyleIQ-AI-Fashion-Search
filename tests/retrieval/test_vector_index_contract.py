"""Unit tests for Phase 4.12 vector search contract."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from productiq.exceptions.base import SemanticRetrievalError
from productiq.retrieval.vector_index_contract import (
    VectorSearchPrimitiveRequest,
    cosine_distance_to_similarity,
    validate_query_embedding_dimension,
    validate_query_embedding_values,
)


def test_cosine_distance_to_similarity() -> None:
    assert cosine_distance_to_similarity(0.0) == pytest.approx(1.0)
    assert cosine_distance_to_similarity(1.0) == pytest.approx(0.0)


def test_validate_query_embedding_dimension() -> None:
    validate_query_embedding_dimension(384)
    with pytest.raises(SemanticRetrievalError):
        validate_query_embedding_dimension(128)


def test_validate_query_embedding_values_rejects_zero_norm() -> None:
    with pytest.raises(SemanticRetrievalError):
        validate_query_embedding_values(tuple(0.0 for _ in range(384)))


def test_vector_search_primitive_request_accepts_unit_vector() -> None:
    values = tuple([1.0] + [0.0] * 383)
    request = VectorSearchPrimitiveRequest(query_vector=values, top_k=10)
    assert request.top_k == 10
    assert len(request.query_vector) == 384


def test_vector_search_primitive_request_rejects_invalid_top_k() -> None:
    values = tuple([1.0] + [0.0] * 383)
    with pytest.raises(ValidationError):
        VectorSearchPrimitiveRequest(query_vector=values, top_k=0)
