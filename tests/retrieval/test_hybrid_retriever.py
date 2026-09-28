"""Unit tests for Phase 4.15 hybrid candidate retrieval."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from productiq.exceptions.base import LexicalRetrievalError
from productiq.representation.query_contract import build_query_representation
from productiq.retrieval.contracts import (
    RetrievalCandidate,
    RetrievalMethod,
    RetrievalRequest,
    RetrievalResponse,
    RetrievalResponseMetadata,
    Retriever,
)
from productiq.retrieval.hybrid import (
    build_hybrid_retrieval_response,
    hybrid_candidate_from_native_scores,
    union_lexical_and_semantic_candidates,
)
from productiq.retrieval.hybrid_retriever import HybridRetriever, create_hybrid_retriever


def _request(top_k: int = 10) -> RetrievalRequest:
    return RetrievalRequest(query=build_query_representation("black nike shoes"), top_k=top_k)


def _bm25_candidate(product_id: str, score: float) -> RetrievalCandidate:
    return RetrievalCandidate(product_id=product_id, score=score, method=RetrievalMethod.BM25)


def _vector_candidate(product_id: str, score: float) -> RetrievalCandidate:
    return RetrievalCandidate(product_id=product_id, score=score, method=RetrievalMethod.VECTOR)


def _response(
    candidates: tuple[RetrievalCandidate, ...],
    *,
    top_k: int = 10,
) -> RetrievalResponse:
    return RetrievalResponse(
        candidates=candidates,
        metadata=RetrievalResponseMetadata(requested_top_k=top_k),
    )


@dataclass
class RecordingRetriever:
    method: RetrievalMethod
    ranking: tuple[tuple[str, float], ...]
    calls: list[RetrievalRequest] = field(default_factory=list)
    fail_with: Exception | None = None

    def retrieve(self, request: RetrievalRequest) -> RetrievalResponse:
        self.calls.append(request)
        if self.fail_with is not None:
            raise self.fail_with
        if self.method is RetrievalMethod.BM25:
            candidates = tuple(_bm25_candidate(pid, score) for pid, score in self.ranking)
        else:
            candidates = tuple(_vector_candidate(pid, score) for pid, score in self.ranking)
        top = candidates[: request.top_k]
        return _response(top, top_k=request.top_k)


def test_union_both_retrievers_return_candidates() -> None:
    lexical = _response((_bm25_candidate("P1", 7.4), _bm25_candidate("P2", 5.2)))
    semantic = _response((_vector_candidate("P1", 0.84), _vector_candidate("P3", 0.79)))
    candidates, stats = union_lexical_and_semantic_candidates(lexical, semantic, requested_top_k=10)
    assert len(candidates) == 3
    assert stats.overlap_count == 1
    assert stats.unique_candidate_count == 3


def test_bm25_only_candidate_preserved() -> None:
    candidate = hybrid_candidate_from_native_scores("P2", bm25_score=5.2, vector_score=None)
    assert candidate.bm25_score == pytest.approx(5.2)
    assert candidate.vector_score is None
    assert candidate.score == pytest.approx(5.2)
    assert candidate.retrieval_methods == (RetrievalMethod.BM25,)


def test_vector_only_candidate_preserved() -> None:
    candidate = hybrid_candidate_from_native_scores("P3", bm25_score=None, vector_score=0.79)
    assert candidate.vector_score == pytest.approx(0.79)
    assert candidate.bm25_score is None
    assert candidate.score == pytest.approx(0.79)
    assert candidate.retrieval_methods == (RetrievalMethod.VECTOR,)


def test_overlap_deduplicated_with_both_native_scores() -> None:
    lexical = _response((_bm25_candidate("P1", 7.4),))
    semantic = _response((_vector_candidate("P1", 0.84),))
    candidates, stats = union_lexical_and_semantic_candidates(lexical, semantic, requested_top_k=10)
    assert len(candidates) == 1
    assert stats.overlap_count == 1
    merged = candidates[0]
    assert merged.product_id == "P1"
    assert merged.bm25_score == pytest.approx(7.4)
    assert merged.vector_score == pytest.approx(0.84)
    assert merged.retrieval_methods == (RetrievalMethod.BM25, RetrievalMethod.VECTOR)
    assert merged.score == 0.0


def test_native_scores_not_added_together() -> None:
    merged = hybrid_candidate_from_native_scores("P1", bm25_score=7.4, vector_score=0.84)
    assert merged.score != pytest.approx(7.4 + 0.84)
    assert merged.score == 0.0


def test_hybrid_retriever_passes_same_top_k_to_both() -> None:
    lexical = RecordingRetriever(RetrievalMethod.BM25, (("A", 1.0),))
    semantic = RecordingRetriever(RetrievalMethod.VECTOR, (("B", 0.5),))
    retriever = HybridRetriever(lexical_retriever=lexical, semantic_retriever=semantic)
    retriever.retrieve(_request(top_k=25))
    assert len(lexical.calls) == 1
    assert len(semantic.calls) == 1
    assert lexical.calls[0].top_k == 25
    assert semantic.calls[0].top_k == 25


def test_union_not_truncated_to_top_k() -> None:
    lexical = RecordingRetriever(
        RetrievalMethod.BM25,
        tuple((f"B{i}", float(i)) for i in range(5)),
    )
    semantic = RecordingRetriever(
        RetrievalMethod.VECTOR,
        tuple((f"V{i}", 0.1 * i) for i in range(1, 6)),
    )
    retriever = HybridRetriever(lexical_retriever=lexical, semantic_retriever=semantic)
    response = retriever.retrieve(_request(top_k=5))
    assert response.candidate_count == 10
    assert response.metadata is not None
    assert response.metadata.unique_candidate_count == 10


def test_bm25_empty_semantic_only() -> None:
    lexical = RecordingRetriever(RetrievalMethod.BM25, ())
    semantic = RecordingRetriever(RetrievalMethod.VECTOR, (("V1", 0.9),))
    response = HybridRetriever(lexical, semantic).retrieve(_request())
    assert [c.product_id for c in response.candidates] == ["V1"]
    assert response.candidates[0].retrieval_methods == (RetrievalMethod.VECTOR,)


def test_semantic_empty_bm25_only() -> None:
    lexical = RecordingRetriever(RetrievalMethod.BM25, (("B1", 3.0),))
    semantic = RecordingRetriever(RetrievalMethod.VECTOR, ())
    response = HybridRetriever(lexical, semantic).retrieve(_request())
    assert [c.product_id for c in response.candidates] == ["B1"]


def test_both_empty() -> None:
    lexical = RecordingRetriever(RetrievalMethod.BM25, ())
    semantic = RecordingRetriever(RetrievalMethod.VECTOR, ())
    response = HybridRetriever(lexical, semantic).retrieve(_request(top_k=7))
    assert response.candidates == ()
    assert response.metadata is not None
    assert response.metadata.requested_top_k == 7


def test_lexical_failure_propagates() -> None:
    lexical = RecordingRetriever(RetrievalMethod.BM25, (), fail_with=LexicalRetrievalError("bm25 down"))
    semantic = RecordingRetriever(RetrievalMethod.VECTOR, (("V1", 0.5),))
    retriever = HybridRetriever(lexical, semantic)
    with pytest.raises(LexicalRetrievalError, match="bm25 down"):
        retriever.retrieve(_request())


def test_semantic_failure_propagates() -> None:
    from productiq.exceptions.base import SemanticRetrievalError

    lexical = RecordingRetriever(RetrievalMethod.BM25, (("B1", 1.0),))
    semantic = RecordingRetriever(
        RetrievalMethod.VECTOR,
        (),
        fail_with=SemanticRetrievalError("semantic down"),
    )
    retriever = HybridRetriever(lexical, semantic)
    with pytest.raises(SemanticRetrievalError, match="semantic down"):
        retriever.retrieve(_request())


def test_deterministic_order_bm25_first_then_vector_only() -> None:
    lexical = _response((_bm25_candidate("B1", 1.0), _bm25_candidate("BOTH", 2.0)))
    semantic = _response((_vector_candidate("V1", 0.5), _vector_candidate("BOTH", 0.9)))
    first, _ = union_lexical_and_semantic_candidates(lexical, semantic, requested_top_k=10)
    second, _ = union_lexical_and_semantic_candidates(lexical, semantic, requested_top_k=10)
    assert [c.product_id for c in first] == [c.product_id for c in second] == ["B1", "BOTH", "V1"]


def test_hybrid_metadata_statistics() -> None:
    lexical = _response((_bm25_candidate("A", 1.0), _bm25_candidate("B", 2.0)))
    semantic = _response((_vector_candidate("B", 0.5), _vector_candidate("C", 0.4)))
    response = build_hybrid_retrieval_response(lexical, semantic, requested_top_k=50)
    assert response.metadata is not None
    assert response.metadata.lexical_candidate_count == 2
    assert response.metadata.semantic_candidate_count == 2
    assert response.metadata.unique_candidate_count == 3
    assert response.metadata.overlap_count == 1


def test_create_hybrid_retriever_protocol() -> None:
    lexical = RecordingRetriever(RetrievalMethod.BM25, (("X", 1.0),))
    semantic = RecordingRetriever(RetrievalMethod.VECTOR, (("Y", 0.2),))
    retriever = create_hybrid_retriever(lexical, semantic)
    assert isinstance(retriever, Retriever)


def test_conflicting_bm25_scores_fail() -> None:
    lexical = _response((_bm25_candidate("P1", 1.0), _bm25_candidate("P1", 2.0)))
    semantic = _response(())
    with pytest.raises(ValueError, match="conflicting BM25"):
        union_lexical_and_semantic_candidates(lexical, semantic, requested_top_k=5)
