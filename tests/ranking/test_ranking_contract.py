"""Tests for Phase 10.1 ranking contracts."""

from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from productiq.exceptions import RankingError
from productiq.ranking.adapters import (
    ranking_candidate_from_retrieval,
    ranking_candidates_from_retrieval_response,
    ranking_request_from_retrieval_response,
)
from productiq.ranking.config import DEFAULT_RANKING_VERSION, RankingConfig
from productiq.ranking.contracts import (
    RankedCandidate,
    RankingCandidate,
    RankingRequest,
    RankingResponse,
    ranking_request_to_dict,
)
from productiq.ranking.invariants import (
    apply_ranking_top_k,
    deterministic_ranking_sort_key,
    ranking_output_limit,
    validate_unique_ranking_product_ids,
)
from productiq.representation.query_contract import build_query_representation
from productiq.retrieval.contracts import (
    RetrievalCandidate,
    RetrievalMethod,
    RetrievalResponse,
    RetrievalResponseMetadata,
)


def _query():
    return build_query_representation("nike running shoes")


def _retrieval_candidate(
    product_id: str,
    *,
    fusion: float | None = None,
) -> RetrievalCandidate:
    if fusion is not None:
        return RetrievalCandidate(
            product_id=product_id,
            score=fusion,
            fusion_score=fusion,
            method=RetrievalMethod.HYBRID,
            retrieval_methods=(RetrievalMethod.BM25, RetrievalMethod.VECTOR),
            bm25_score=1.0,
            vector_score=0.5,
            bm25_rank=1,
            vector_rank=2,
        )
    return RetrievalCandidate(product_id=product_id, score=0.9, method=RetrievalMethod.VECTOR)


def _ranking_candidate(product_id: str) -> RankingCandidate:
    return ranking_candidate_from_retrieval(_retrieval_candidate(product_id))


def test_ranking_candidate_valid() -> None:
    candidate = _ranking_candidate("P100")
    assert candidate.product_id == "P100"
    assert candidate.retrieval.method is RetrievalMethod.VECTOR


def test_ranking_candidate_rejects_mismatched_product_id() -> None:
    retrieval = _retrieval_candidate("P1")
    with pytest.raises(ValidationError, match="product_id must match"):
        RankingCandidate(product_id="P2", retrieval=retrieval)


@pytest.mark.parametrize("bad_product_id", ["", "   "])
def test_ranking_candidate_rejects_empty_product_id(bad_product_id: str) -> None:
    retrieval = RetrievalCandidate(product_id="P1", score=1.0, method=RetrievalMethod.BM25)
    with pytest.raises(ValidationError):
        RankingCandidate(product_id=bad_product_id, retrieval=retrieval)


def test_ranking_request_accepts_empty_candidates() -> None:
    request = RankingRequest(query=_query(), candidates=(), top_k=10)
    assert request.candidates == ()
    assert request.top_k == 10


def test_ranking_request_rejects_duplicate_product_ids() -> None:
    with pytest.raises(ValidationError, match="unique product_id"):
        RankingRequest(
            query=_query(),
            candidates=(_ranking_candidate("P1"), _ranking_candidate("P1")),
            top_k=5,
        )


@pytest.mark.parametrize("invalid_top_k", [0, -3])
def test_ranking_request_rejects_invalid_top_k(invalid_top_k: int) -> None:
    with pytest.raises(ValidationError):
        RankingRequest(query=_query(), candidates=(), top_k=invalid_top_k)


def test_ranking_request_is_frozen() -> None:
    request = RankingRequest(query=_query(), candidates=(), top_k=3)
    with pytest.raises(ValidationError):
        request.top_k = 5  # type: ignore[misc]


def test_ranking_config_defaults() -> None:
    config = RankingConfig()
    assert config.ranking_version == DEFAULT_RANKING_VERSION
    assert config.tie_break_key == "product_id"


def test_ranking_config_rejects_empty_version() -> None:
    with pytest.raises(ValidationError):
        RankingConfig(ranking_version="")


def test_ranked_candidate_finite_score() -> None:
    ranked = RankedCandidate(
        product_id="P1",
        rank=1,
        ranking_score=0.42,
        candidate=_ranking_candidate("P1"),
    )
    assert ranked.ranking_score == pytest.approx(0.42)


@pytest.mark.parametrize("bad_score", [math.nan, math.inf, -math.inf])
def test_ranked_candidate_rejects_non_finite_score(bad_score: float) -> None:
    with pytest.raises(ValidationError):
        RankedCandidate(
            product_id="P1",
            rank=1,
            ranking_score=bad_score,
            candidate=_ranking_candidate("P1"),
        )


def test_ranking_response_top_k_semantics() -> None:
    rows = tuple(
        RankedCandidate(
            product_id=f"P{index}",
            rank=index,
            ranking_score=float(index),
            candidate=_ranking_candidate(f"P{index}"),
        )
        for index in range(1, 4)
    )
    response = RankingResponse(ranked_candidates=rows, requested_top_k=10, config=RankingConfig())
    assert response.returned_candidate_count == 3


def test_ranking_response_rejects_excess_rows_for_top_k() -> None:
    rows = tuple(
        RankedCandidate(
            product_id=f"P{index}",
            rank=index,
            ranking_score=1.0,
            candidate=_ranking_candidate(f"P{index}"),
        )
        for index in range(1, 4)
    )
    with pytest.raises(ValidationError, match="requested_top_k"):
        RankingResponse(ranked_candidates=rows, requested_top_k=2, config=RankingConfig())


def test_ranking_output_limit() -> None:
    assert ranking_output_limit(candidate_count=5, top_k=3) == 3
    assert ranking_output_limit(candidate_count=2, top_k=10) == 2


def test_apply_ranking_top_k_does_not_mutate_input() -> None:
    rows = tuple(
        RankedCandidate(
            product_id=f"P{index}",
            rank=index,
            ranking_score=1.0,
            candidate=_ranking_candidate(f"P{index}"),
        )
        for index in range(1, 5)
    )
    original = rows
    trimmed = apply_ranking_top_k(rows, top_k=2)
    assert len(trimmed) == 2
    assert rows == original


def test_deterministic_tie_break_by_product_id() -> None:
    config = RankingConfig()
    key_a = deterministic_ranking_sort_key(ranking_score=0.5, product_id="A", config=config)
    key_b = deterministic_ranking_sort_key(ranking_score=0.5, product_id="B", config=config)
    assert key_a < key_b
    assert sorted([key_b, key_a]) == [key_a, key_b]


def test_validate_unique_ranking_product_ids_raises() -> None:
    with pytest.raises(RankingError, match="unique product_id"):
        validate_unique_ranking_product_ids((_ranking_candidate("P1"), _ranking_candidate("P1")))


def test_ranking_request_input_tuple_not_mutated_by_construction() -> None:
    candidates = (_ranking_candidate("A"), _ranking_candidate("B"))
    snapshot = candidates
    RankingRequest(query=_query(), candidates=candidates, top_k=2)
    assert candidates == snapshot


def test_retrieval_adapter_preserves_provenance() -> None:
    retrieval = _retrieval_candidate("P9", fusion=0.03)
    ranking = ranking_candidate_from_retrieval(retrieval)
    assert ranking.retrieval.fusion_score == pytest.approx(0.03)
    assert ranking.retrieval.bm25_rank == 1


def test_ranking_request_from_retrieval_response() -> None:
    retrieval_rows = (
        _retrieval_candidate("P1", fusion=0.9),
        _retrieval_candidate("P2", fusion=0.8),
    )
    response = RetrievalResponse(
        candidates=retrieval_rows,
        metadata=RetrievalResponseMetadata(requested_top_k=10),
    )
    request = ranking_request_from_retrieval_response(
        query=_query(),
        response=response,
        top_k=5,
    )
    assert len(request.candidates) == 2
    assert request.candidates[0].retrieval.fusion_score == pytest.approx(0.9)
    payload = ranking_request_to_dict(request)
    assert payload["top_k"] == 5


def test_ranking_candidates_from_retrieval_response_preserves_order() -> None:
    response = RetrievalResponse(
        candidates=(
            _retrieval_candidate("A"),
            _retrieval_candidate("B"),
        ),
    )
    ranking_rows = ranking_candidates_from_retrieval_response(response)
    assert [row.product_id for row in ranking_rows] == ["A", "B"]


def test_empty_candidate_collection_eventually_empty_result() -> None:
    request = RankingRequest(query=_query(), candidates=(), top_k=5)
    response = RankingResponse(ranked_candidates=(), requested_top_k=request.top_k, config=request.config)
    assert response.returned_candidate_count == 0
