"""Tests for Phase 4.7 BM25 candidate retrieval."""

from __future__ import annotations

import math
import os
from pathlib import Path

import pytest

from productiq.representation.query_contract import (
    QueryFilterConstraints,
    build_query_representation,
)
from productiq.retrieval import (
    BM25Retriever,
    LexicalIndexDocument,
    RetrievalMethod,
    RetrievalRequest,
    Retriever,
    build_inverted_lexical_index,
    create_bm25_retriever,
)
from productiq.retrieval.bm25 import BM25Config
from productiq.retrieval.bm25_retriever import create_bm25_retriever_from_index_path


def _mini_index():
    return build_inverted_lexical_index(
        [
            LexicalIndexDocument(product_id="P1", lexical_text="nike black running shoes"),
            LexicalIndexDocument(product_id="P2", lexical_text="nike white shoes"),
            LexicalIndexDocument(product_id="P3", lexical_text="adidas black running shoes"),
            LexicalIndexDocument(product_id="P4", lexical_text="adidas sandals"),
        ]
    )


def _request(query_text: str, *, top_k: int = 10, constraints: QueryFilterConstraints | None = None):
    return RetrievalRequest(
        query=build_query_representation(query_text, constraints=constraints),
        top_k=top_k,
    )


def test_bm25_retriever_satisfies_retriever_protocol() -> None:
    retriever = create_bm25_retriever(_mini_index())
    assert isinstance(retriever, Retriever)


def test_basic_lexical_query_returns_bm25_candidates() -> None:
    retriever = create_bm25_retriever(_mini_index())
    response = retriever.retrieve(_request("nike shoes"))
    assert response.candidate_count >= 1
    assert all(candidate.method is RetrievalMethod.BM25 for candidate in response.candidates)
    assert all(math.isfinite(candidate.score) for candidate in response.candidates)


def test_nike_shoes_prefers_nike_products() -> None:
    retriever = create_bm25_retriever(_mini_index())
    response = retriever.retrieve(_request("nike shoes", top_k=4))
    product_ids = [candidate.product_id for candidate in response.candidates]
    assert "P1" in product_ids
    assert "P2" in product_ids
    if "P3" in product_ids:
        assert product_ids.index("P1") < product_ids.index("P3")


def test_ordering_score_desc_then_product_id() -> None:
    retriever = create_bm25_retriever(_mini_index())
    response = retriever.retrieve(_request("black running shoes", top_k=10))
    scores = [candidate.score for candidate in response.candidates]
    assert scores == sorted(scores, reverse=True)
    for left, right in zip(response.candidates, response.candidates[1:], strict=False):
        if left.score == right.score:
            assert left.product_id < right.product_id


def test_top_k_respected() -> None:
    retriever = create_bm25_retriever(_mini_index())
    response = retriever.retrieve(_request("shoes", top_k=2))
    assert len(response.candidates) <= 2
    assert response.metadata is not None
    assert response.metadata.requested_top_k == 2


def test_top_k_larger_than_available_returns_all() -> None:
    retriever = create_bm25_retriever(_mini_index())
    response = retriever.retrieve(_request("nike", top_k=100))
    assert len(response.candidates) <= 3


def test_unknown_terms_return_empty_response() -> None:
    retriever = create_bm25_retriever(_mini_index())
    response = retriever.retrieve(_request("xyzabc", top_k=5))
    assert response.candidates == ()
    assert response.metadata is not None


def test_empty_lexical_query_returns_empty_response() -> None:
    retriever = create_bm25_retriever(_mini_index())
    request = RetrievalRequest(
        query=build_query_representation("nike shoes", lexical_text="!!!"),
        top_k=5,
    )
    response = retriever.retrieve(request)
    assert response.candidates == ()


def test_duplicate_query_terms_do_not_duplicate_candidates() -> None:
    retriever = create_bm25_retriever(_mini_index())
    response = retriever.retrieve(_request("nike nike shoes", top_k=10))
    product_ids = [candidate.product_id for candidate in response.candidates]
    assert len(product_ids) == len(set(product_ids))


def test_uses_posting_union_not_full_corpus_scan(monkeypatch: pytest.MonkeyPatch) -> None:
    index = _mini_index()
    retriever = create_bm25_retriever(index)
    scanned_all = False

    original_score = retriever.scorer.score_lexical_query

    def tracked_score(query_lexical_text: str, *, candidate_product_ids=None):
        nonlocal scanned_all
        if candidate_product_ids is None:
            scanned_all = True
        return original_score(
            query_lexical_text,
            candidate_product_ids=candidate_product_ids,
        )

    monkeypatch.setattr(retriever.scorer, "score_lexical_query", tracked_score)
    retriever.retrieve(_request("nike shoes", top_k=5))
    assert scanned_all is False


def test_constraints_not_applied_in_bm25_retriever() -> None:
    index = _mini_index()
    retriever = create_bm25_retriever(index)
    with_constraints = retriever.retrieve(
        _request(
            "nike shoes",
            constraints=QueryFilterConstraints(brand="Adidas"),
        )
    )
    without_constraints = retriever.retrieve(_request("nike shoes"))
    assert [c.product_id for c in with_constraints.candidates] == [
        c.product_id for c in without_constraints.candidates
    ]


def test_semantic_intent_does_not_change_bm25_retrieval() -> None:
    index = _mini_index()
    retriever = create_bm25_retriever(index)
    base = retriever.retrieve(
        RetrievalRequest(
            query=build_query_representation(
                "nike shoes",
                semantic_text="completely unrelated semantic payload",
            ),
            top_k=5,
        )
    )
    plain = retriever.retrieve(_request("nike shoes", top_k=5))
    assert [c.product_id for c in base.candidates] == [c.product_id for c in plain.candidates]


def test_deterministic_repeated_calls() -> None:
    retriever = create_bm25_retriever(_mini_index())
    first = retriever.retrieve(_request("nike black shoes", top_k=5))
    second = retriever.retrieve(_request("nike black shoes", top_k=5))
    assert first == second


def test_bm25_config_respected() -> None:
    index = _mini_index()
    default_retriever = create_bm25_retriever(index)
    custom_retriever = BM25Retriever(index, config=BM25Config(k1=0.0, b=0.0))
    default_response = default_retriever.retrieve(_request("nike shoes", top_k=2))
    custom_response = custom_retriever.retrieve(_request("nike shoes", top_k=2))
    assert default_response.candidates
    assert custom_response.candidates
    assert default_response.candidates[0].score != custom_response.candidates[0].score


def test_candidate_metadata_not_product_attributes() -> None:
    retriever = create_bm25_retriever(_mini_index())
    response = retriever.retrieve(_request("nike", top_k=3))
    for candidate in response.candidates:
        assert candidate.metadata is None


@pytest.mark.skipif(
    os.environ.get("PRODUCTIQ_BM25_RETRIEVER_SMOKE") != "1",
    reason="Set PRODUCTIQ_BM25_RETRIEVER_SMOKE=1 to smoke-test persisted index",
)
def test_smoke_persisted_index_retrieval() -> None:
    index_path = Path("resources/processed/bm25_lexical_index.pkl")
    if not index_path.is_file():
        pytest.skip("persisted BM25 index not present")
    retriever = create_bm25_retriever_from_index_path(index_path)
    response = retriever.retrieve(_request("nike black shoes", top_k=5))
    assert len(response.candidates) <= 5
    assert all(candidate.method is RetrievalMethod.BM25 for candidate in response.candidates)
