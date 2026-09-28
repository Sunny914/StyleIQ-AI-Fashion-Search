"""Unit tests for Phase 4.16 Reciprocal Rank Fusion."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from pydantic import ValidationError

from productiq.exceptions.base import SemanticRetrievalError
from productiq.representation.query_contract import build_query_representation
from productiq.retrieval.contracts import (
    RetrievalCandidate,
    RetrievalMethod,
    RetrievalRequest,
    RetrievalResponse,
    RetrievalResponseMetadata,
    Retriever,
)
from productiq.retrieval.exceptions import RetrievalError
from productiq.retrieval.rrf_config import DEFAULT_RRF_RANK_CONSTANT, RRFConfig
from productiq.retrieval.rrf_fusion import (
    build_rrf_fused_retrieval_response,
    compute_rrf_score,
    fuse_lexical_and_semantic_responses,
    rrf_contribution,
)
from productiq.retrieval.rrf_hybrid_retriever import RRFHybridRetriever, create_rrf_hybrid_retriever


def test_rrf_contribution_formula_k60() -> None:
    assert rrf_contribution(rank=1, rank_constant=60) == pytest.approx(1.0 / 61.0)
    assert rrf_contribution(rank=5, rank_constant=60) == pytest.approx(1.0 / 65.0)


def test_rrf_rank_is_one_based() -> None:
    assert rrf_contribution(rank=1, rank_constant=10) == pytest.approx(1.0 / 11.0)
    with pytest.raises(ValueError):
        rrf_contribution(rank=0, rank_constant=10)


def test_rrf_config_default_k() -> None:
    assert RRFConfig().rank_constant == DEFAULT_RRF_RANK_CONSTANT == 60


def test_rrf_config_custom_k() -> None:
    assert RRFConfig(rank_constant=10).rank_constant == 10


def test_rrf_config_rejects_invalid_k() -> None:
    with pytest.raises(ValidationError):
        RRFConfig(rank_constant=0)


def _bm25(product_id: str, score: float = 1.0) -> RetrievalCandidate:
    return RetrievalCandidate(product_id=product_id, score=score, method=RetrievalMethod.BM25)


def _vector(product_id: str, score: float = 0.5) -> RetrievalCandidate:
    return RetrievalCandidate(product_id=product_id, score=score, method=RetrievalMethod.VECTOR)


def _resp(*candidates: RetrievalCandidate, top_k: int = 10) -> RetrievalResponse:
    return RetrievalResponse(
        candidates=candidates,
        metadata=RetrievalResponseMetadata(requested_top_k=top_k),
    )


def test_documented_rrf_rank_formula() -> None:
    p1 = 1 / 61 + 1 / 65
    p2 = 1 / 62
    p3 = 1 / 70 + 1 / 61
    p4 = 1 / 62
    assert compute_rrf_score(bm25_rank=1, vector_rank=5, rank_constant=60) == pytest.approx(p1)
    assert compute_rrf_score(bm25_rank=2, vector_rank=None, rank_constant=60) == pytest.approx(p2)
    assert compute_rrf_score(bm25_rank=10, vector_rank=1, rank_constant=60) == pytest.approx(p3)
    assert compute_rrf_score(bm25_rank=None, vector_rank=2, rank_constant=60) == pytest.approx(p4)


def test_documented_rrf_example_ordering() -> None:
    lexical = _resp(_bm25("P1"), _bm25("P2"), _bm25("P3"))
    semantic = _resp(_vector("P3"), _vector("P4"), _vector("P1"))
    p1 = 1 / 61 + 1 / 63
    p3 = 1 / 63 + 1 / 61
    candidates, _ = fuse_lexical_and_semantic_responses(
        lexical, semantic, config=RRFConfig(rank_constant=60), output_top_k=10
    )
    assert [c.product_id for c in candidates] == ["P1", "P3", "P2", "P4"]
    assert candidates[0].fusion_score == pytest.approx(p1)
    assert candidates[1].fusion_score == pytest.approx(p3)
    assert candidates[0].bm25_rank == 1
    assert candidates[0].vector_rank == 3
    assert candidates[1].bm25_rank == 3
    assert candidates[1].vector_rank == 1


def test_native_scores_do_not_change_rrf_when_reordered() -> None:
    lexical = _resp(_bm25("A", score=100.0), _bm25("B", score=1.0))
    semantic = _resp(_vector("A", score=0.01), _vector("B", score=0.99))
    low_lexical = _resp(_bm25("A", score=1.0), _bm25("B", score=100.0))
    fused_high, _ = fuse_lexical_and_semantic_responses(
        lexical, semantic, config=RRFConfig(rank_constant=60), output_top_k=2
    )
    fused_low, _ = fuse_lexical_and_semantic_responses(
        low_lexical, semantic, config=RRFConfig(rank_constant=60), output_top_k=2
    )
    assert [c.fusion_score for c in fused_high] == [c.fusion_score for c in fused_low]


def test_top_k_truncation_after_fusion() -> None:
    lexical = _resp(*(_bm25(f"B{i}") for i in range(5)))
    semantic = _resp(*(_vector(f"V{i}") for i in range(5)))
    candidates, stats = fuse_lexical_and_semantic_responses(
        lexical, semantic, config=RRFConfig(rank_constant=60), output_top_k=3
    )
    assert len(candidates) == 3
    assert stats.hybrid_pool_count == 10
    assert stats.fused_candidate_count == 3


def test_duplicate_product_in_source_list_rejected() -> None:
    lexical = _resp(_bm25("P1"), _bm25("P1"))
    semantic = _resp(_vector("P2"))
    with pytest.raises(RetrievalError, match="duplicate"):
        fuse_lexical_and_semantic_responses(
            lexical, semantic, config=RRFConfig(), output_top_k=5
        )


def test_bm25_empty_semantic_only() -> None:
    semantic = _resp(_vector("V1"), _vector("V2"))
    candidates, _ = fuse_lexical_and_semantic_responses(
        _resp(), semantic, config=RRFConfig(rank_constant=60), output_top_k=10
    )
    assert len(candidates) == 2
    assert candidates[0].vector_rank == 1
    assert candidates[0].bm25_rank is None


def test_semantic_empty_bm25_only() -> None:
    lexical = _resp(_bm25("B1"))
    candidates, _ = fuse_lexical_and_semantic_responses(
        lexical, _resp(), config=RRFConfig(rank_constant=60), output_top_k=10
    )
    assert candidates[0].bm25_rank == 1
    assert candidates[0].vector_rank is None


def test_both_empty() -> None:
    response = build_rrf_fused_retrieval_response(
        _resp(),
        _resp(),
        config=RRFConfig(),
        requested_top_k=5,
    )
    assert response.candidates == ()
    assert response.metadata is not None
    assert response.metadata.requested_top_k == 5


def test_fused_candidate_preserves_native_scores_and_ranks() -> None:
    lexical = _resp(_bm25("X", score=9.5))
    semantic = _resp(_vector("X", score=0.77))
    candidates, _ = fuse_lexical_and_semantic_responses(
        lexical, semantic, config=RRFConfig(rank_constant=60), output_top_k=1
    )
    row = candidates[0]
    assert row.bm25_score == pytest.approx(9.5)
    assert row.vector_score == pytest.approx(0.77)
    assert row.bm25_rank == 1
    assert row.vector_rank == 1
    assert row.retrieval_methods == (RetrievalMethod.BM25, RetrievalMethod.VECTOR)
    assert row.fusion_score != row.bm25_score
    assert row.score == row.fusion_score


def test_product_id_tie_break() -> None:
    lexical = _resp(_bm25("A"))
    semantic = _resp(_vector("B"))
    candidates, _ = fuse_lexical_and_semantic_responses(
        lexical, semantic, config=RRFConfig(rank_constant=60), output_top_k=2
    )
    assert candidates[0].fusion_score == pytest.approx(candidates[1].fusion_score)
    assert [c.product_id for c in candidates] == ["A", "B"]


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
            cands = tuple(_bm25(pid, score) for pid, score in self.ranking)
        else:
            cands = tuple(_vector(pid, score) for pid, score in self.ranking)
        return _resp(*cands[: request.top_k], top_k=request.top_k)


def test_rrf_hybrid_passes_top_k_to_both_retrievers() -> None:
    lexical = RecordingRetriever(RetrievalMethod.BM25, (("A", 1.0),))
    semantic = RecordingRetriever(RetrievalMethod.VECTOR, (("B", 0.5),))
    retriever = create_rrf_hybrid_retriever(lexical, semantic)
    request = RetrievalRequest(query=build_query_representation("test"), top_k=25)
    retriever.retrieve(request)
    assert lexical.calls[0].top_k == 25
    assert semantic.calls[0].top_k == 25


def test_rrf_hybrid_failure_propagation() -> None:
    from productiq.exceptions.base import LexicalRetrievalError

    lexical = RecordingRetriever(RetrievalMethod.BM25, (), fail_with=LexicalRetrievalError("x"))
    semantic = RecordingRetriever(RetrievalMethod.VECTOR, (("V", 0.1),))
    with pytest.raises(LexicalRetrievalError):
        RRFHybridRetriever(lexical, semantic, RRFConfig()).retrieve(
            RetrievalRequest(query=build_query_representation("q"), top_k=5)
        )
    semantic.fail_with = SemanticRetrievalError("y")
    lexical.fail_with = None
    with pytest.raises(SemanticRetrievalError):
        RRFHybridRetriever(lexical, semantic, RRFConfig()).retrieve(
            RetrievalRequest(query=build_query_representation("q"), top_k=5)
        )


def test_create_rrf_hybrid_retriever_protocol() -> None:
    lexical = RecordingRetriever(RetrievalMethod.BM25, (("A", 1.0),))
    semantic = RecordingRetriever(RetrievalMethod.VECTOR, (("B", 0.2),))
    assert isinstance(create_rrf_hybrid_retriever(lexical, semantic), Retriever)
