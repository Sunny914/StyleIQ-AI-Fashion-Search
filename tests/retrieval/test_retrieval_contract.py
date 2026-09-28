"""Tests for Phase 4.2 search and retrieval contract."""

from __future__ import annotations

import inspect
import math
from dataclasses import dataclass

import pytest
from pydantic import ValidationError

from productiq.representation.query_contract import QueryRepresentation, build_query_representation
from productiq.retrieval import (
    RetrievalCandidate,
    RetrievalMethod,
    RetrievalRequest,
    RetrievalResponse,
    RetrievalResponseMetadata,
    Retriever,
    retrieval_request_to_dict,
    retrieval_response_to_dict,
)


def _sample_query() -> QueryRepresentation:
    return build_query_representation("nike cotton shirt")


def test_retrieval_request_accepts_valid_query_and_top_k() -> None:
    request = RetrievalRequest(query=_sample_query(), top_k=200)
    assert request.query.query_text == "nike cotton shirt"
    assert request.top_k == 200


@pytest.mark.parametrize("invalid_top_k", [0, -1, -100])
def test_retrieval_request_rejects_non_positive_top_k(invalid_top_k: int) -> None:
    with pytest.raises(ValidationError):
        RetrievalRequest(query=_sample_query(), top_k=invalid_top_k)


def test_retrieval_request_rejects_invalid_query_type() -> None:
    with pytest.raises(ValidationError):
        RetrievalRequest(query="not a query representation", top_k=10)  # type: ignore[arg-type]


def test_retrieval_request_is_frozen() -> None:
    request = RetrievalRequest(query=_sample_query(), top_k=5)
    with pytest.raises(ValidationError):
        request.top_k = 10  # type: ignore[misc]


def test_retrieval_request_does_not_parse_raw_query_strings() -> None:
    assert "query_text" not in RetrievalRequest.model_fields
    payload = retrieval_request_to_dict(RetrievalRequest(query=_sample_query(), top_k=3))
    assert "query" in payload
    assert isinstance(payload["query"], dict)


def test_retrieval_candidate_valid_bm25_and_vector_scores() -> None:
    bm25 = RetrievalCandidate(product_id="P123", score=14.82, method=RetrievalMethod.BM25)
    vector = RetrievalCandidate(product_id="P123", score=0.87, method=RetrievalMethod.VECTOR)
    assert bm25.method is RetrievalMethod.BM25
    assert vector.method is RetrievalMethod.VECTOR
    assert bm25.score != vector.score


@pytest.mark.parametrize("bad_score", [math.nan, math.inf, -math.inf])
def test_retrieval_candidate_rejects_non_finite_score(bad_score: float) -> None:
    with pytest.raises(ValidationError):
        RetrievalCandidate(product_id="P1", score=bad_score, method=RetrievalMethod.BM25)


@pytest.mark.parametrize("bad_product_id", ["", "   "])
def test_retrieval_candidate_rejects_empty_product_id(bad_product_id: str) -> None:
    with pytest.raises(ValidationError):
        RetrievalCandidate(product_id=bad_product_id, score=1.0, method=RetrievalMethod.VECTOR)


def test_retrieval_candidate_preserves_provenance_metadata() -> None:
    candidate = RetrievalCandidate(
        product_id="P99",
        score=2.5,
        method=RetrievalMethod.HYBRID,
        retrieval_methods=(RetrievalMethod.BM25,),
        bm25_score=2.5,
        metadata={"stage": "union", "engine": "stub"},
    )
    assert candidate.metadata == {"stage": "union", "engine": "stub"}


def test_retrieval_candidate_identity_is_product_id_only() -> None:
    fields = set(RetrievalCandidate.model_fields)
    assert "product_id" in fields
    assert "url" not in fields
    assert "embedding_id" not in fields


def test_retrieval_candidate_is_frozen() -> None:
    candidate = RetrievalCandidate(product_id="P1", score=1.0, method=RetrievalMethod.BM25)
    with pytest.raises(ValidationError):
        candidate.score = 2.0  # type: ignore[misc]


def test_retrieval_response_preserves_candidate_order() -> None:
    first = RetrievalCandidate(product_id="A", score=10.0, method=RetrievalMethod.BM25)
    second = RetrievalCandidate(product_id="B", score=9.0, method=RetrievalMethod.BM25)
    third = RetrievalCandidate(product_id="C", score=8.0, method=RetrievalMethod.BM25)
    response = RetrievalResponse(candidates=(first, second, third))
    assert [c.product_id for c in response.candidates] == ["A", "B", "C"]


def test_retrieval_response_candidate_count() -> None:
    candidates = tuple(
        RetrievalCandidate(product_id=f"P{i}", score=float(i), method=RetrievalMethod.VECTOR)
        for i in range(3)
    )
    response = RetrievalResponse(candidates=candidates)
    assert response.candidate_count == 3
    assert len(response.candidates) == 3


def test_retrieval_response_metadata_provenance() -> None:
    response = RetrievalResponse(
        candidates=(),
        metadata=RetrievalResponseMetadata(requested_top_k=50),
    )
    dumped = retrieval_response_to_dict(response)
    assert dumped["metadata"]["requested_top_k"] == 50


def test_hybrid_candidate_dual_native_scores_use_zero_score_field() -> None:
    candidate = RetrievalCandidate(
        product_id="P1",
        score=0.0,
        method=RetrievalMethod.HYBRID,
        retrieval_methods=(RetrievalMethod.BM25, RetrievalMethod.VECTOR),
        bm25_score=7.4,
        vector_score=0.84,
    )
    assert candidate.score == 0.0
    assert candidate.bm25_score == pytest.approx(7.4)
    assert candidate.vector_score == pytest.approx(0.84)


def test_retrieval_response_does_not_reorder_on_construction() -> None:
    low = RetrievalCandidate(product_id="low", score=0.1, method=RetrievalMethod.VECTOR)
    high = RetrievalCandidate(product_id="high", score=0.9, method=RetrievalMethod.VECTOR)
    response = RetrievalResponse(candidates=(low, high))
    assert response.candidates[0].product_id == "low"


def test_retrieval_response_is_frozen() -> None:
    response = RetrievalResponse(candidates=())
    with pytest.raises(ValidationError):
        response.candidates = ()  # type: ignore[misc]


@dataclass(frozen=True)
class _StubRetriever:
    method: RetrievalMethod

    def retrieve(self, request: RetrievalRequest) -> RetrievalResponse:
        candidate = RetrievalCandidate(
            product_id="P-STUB",
            score=1.0,
            method=self.method,
            metadata={"requested_top_k": request.top_k},
        )
        return RetrievalResponse(
            candidates=(candidate,),
            metadata=RetrievalResponseMetadata(requested_top_k=request.top_k),
        )


def test_stub_retriever_conforms_to_retriever_protocol() -> None:
    retriever = _StubRetriever(method=RetrievalMethod.BM25)
    assert isinstance(retriever, Retriever)
    request = RetrievalRequest(query=_sample_query(), top_k=25)
    response = retriever.retrieve(request)
    assert response.candidate_count == 1
    assert response.candidates[0].product_id == "P-STUB"
    assert response.candidates[0].method is RetrievalMethod.BM25


def test_query_representation_unchanged_by_retrieval_request() -> None:
    query = _sample_query()
    before = query.model_dump()
    _ = RetrievalRequest(query=query, top_k=10)
    assert query.model_dump() == before


def test_retrieval_contract_module_has_no_engine_imports() -> None:
    from productiq.retrieval import contracts

    source = inspect.getsource(contracts).lower()
    forbidden_tokens = (
        "sqlalchemy",
        "psycopg",
        "faiss",
        "sentence_transformers",
        "bm25index",
        "postgres",
    )
    for token in forbidden_tokens:
        assert token not in source


def test_retrieval_package_does_not_implement_scoring_fusion() -> None:
    from productiq.retrieval import contracts

    source = inspect.getsource(contracts).lower()
    assert "normalize" not in source
    assert "rerank" not in source
    assert "1 / (k" not in source
    assert "weighted" not in source

