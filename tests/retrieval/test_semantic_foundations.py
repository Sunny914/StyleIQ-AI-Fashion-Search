"""Tests for Phase 4.9 semantic retrieval foundations."""

from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from productiq.exceptions.base import SemanticRetrievalError
from productiq.representation.query_contract import build_query_representation
from productiq.retrieval import (
    RetrievalCandidate,
    RetrievalMethod,
    RetrievalRequest,
    build_retrieval_query_view,
)
from productiq.retrieval.semantic import (
    SemanticRetrievalConfig,
    SemanticSearchHit,
    SemanticSimilarityMetric,
    SemanticVector,
    cosine_similarity,
    semantic_hits_to_retrieval_response,
    semantic_retrieval_alignment,
    semantic_retrieval_candidate,
    semantic_retrieval_text_from_query,
    semantic_retrieval_text_from_request,
    semantic_search_hits_to_retrieval_candidates,
    semantic_vector_from_sequence,
    validate_semantic_retrieval_top_k,
)


def test_semantic_vector_valid_and_frozen() -> None:
    vector = SemanticVector(values=(1.0, 0.0, -1.0))
    assert vector.dimension == 3
    assert vector.to_tuple() == (1.0, 0.0, -1.0)
    with pytest.raises(ValidationError):
        vector.values = (2.0,)  # type: ignore[misc]


def test_semantic_vector_rejects_empty() -> None:
    with pytest.raises(ValidationError):
        SemanticVector(values=())
    with pytest.raises(SemanticRetrievalError):
        semantic_vector_from_sequence([])


def test_semantic_vector_rejects_non_finite() -> None:
    with pytest.raises(ValidationError):
        SemanticVector(values=(1.0, float("nan")))
    with pytest.raises(ValidationError):
        SemanticVector(values=(float("inf"), 1.0))


def test_cosine_identical_vectors() -> None:
    left = (1.0, 2.0, 3.0)
    assert cosine_similarity(left, left) == pytest.approx(1.0)


def test_cosine_orthogonal_vectors() -> None:
    assert cosine_similarity((1.0, 0.0), (0.0, 1.0)) == pytest.approx(0.0)


def test_cosine_opposite_vectors() -> None:
    assert cosine_similarity((1.0, 0.0), (-1.0, 0.0)) == pytest.approx(-1.0)


def test_cosine_symmetry() -> None:
    a = (0.3, 0.4, 0.0)
    b = (0.1, 0.9, 0.2)
    assert cosine_similarity(a, b) == pytest.approx(cosine_similarity(b, a))


def test_cosine_dimension_mismatch() -> None:
    with pytest.raises(SemanticRetrievalError):
        cosine_similarity((1.0, 0.0), (1.0,))


def test_cosine_zero_norm_vector() -> None:
    with pytest.raises(SemanticRetrievalError):
        cosine_similarity((0.0, 0.0), (1.0, 0.0))


def test_cosine_non_finite_input() -> None:
    with pytest.raises(SemanticRetrievalError):
        cosine_similarity((1.0, float("nan")), (1.0, 0.0))


def test_cosine_deterministic() -> None:
    a = SemanticVector(values=(0.2, 0.5, 0.7))
    b = SemanticVector(values=(0.9, 0.1, 0.4))
    first = cosine_similarity(a, b)
    second = cosine_similarity(a, b)
    assert first == second
    assert math.isfinite(first)


def test_semantic_alignment_semantic_text_and_intent() -> None:
    query = build_query_representation(
        "black nike shoes",
        semantic_text="athletic Nike footwear",
    )
    assert semantic_retrieval_text_from_query(query) == "athletic Nike footwear"
    assert semantic_retrieval_alignment() == (("semantic_text", "semantic_intent"),)
    view = build_retrieval_query_view(query)
    assert view.semantic_retrieval_text == query.semantic_intent.text


def test_semantic_text_from_retrieval_request() -> None:
    query = build_query_representation("women dress", semantic_text="casual women dress")
    request = RetrievalRequest(query=query, top_k=10)
    assert semantic_retrieval_text_from_request(request) == "casual women dress"


def test_vector_retrieval_method_and_candidate() -> None:
    candidate = semantic_retrieval_candidate("P1", similarity=0.88)
    assert candidate.method is RetrievalMethod.VECTOR
    assert candidate.score == pytest.approx(0.88)
    assert isinstance(candidate, RetrievalCandidate)


def test_semantic_search_hits_to_response() -> None:
    hits = (
        SemanticSearchHit(product_id="A", similarity=0.9),
        SemanticSearchHit(product_id="B", similarity=0.7),
    )
    candidates = semantic_search_hits_to_retrieval_candidates(hits)
    assert candidates[0].method is RetrievalMethod.VECTOR
    response = semantic_hits_to_retrieval_response(hits, requested_top_k=2)
    assert response.candidate_count == 2
    assert response.metadata is not None
    assert response.metadata.requested_top_k == 2


def test_semantic_retrieval_config_defaults() -> None:
    config = SemanticRetrievalConfig()
    assert config.similarity_metric is SemanticSimilarityMetric.COSINE


def test_validate_semantic_retrieval_top_k() -> None:
    assert validate_semantic_retrieval_top_k(5) == 5
    with pytest.raises(SemanticRetrievalError):
        validate_semantic_retrieval_top_k(0)
