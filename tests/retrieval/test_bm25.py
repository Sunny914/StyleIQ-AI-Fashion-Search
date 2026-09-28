"""Tests for Phase 4.5 BM25 scoring."""

from __future__ import annotations

import math
from itertools import pairwise

import pytest
from pydantic import ValidationError

from productiq.exceptions.base import LexicalRetrievalError
from productiq.representation.query_contract import build_query_representation
from productiq.retrieval import (
    BM25Config,
    BM25CorpusStatistics,
    BM25ScoredCandidate,
    BM25Scorer,
    LexicalIndexDocument,
    RetrievalRequest,
    apply_bm25_top_k,
    bm25_idf,
    build_inverted_lexical_index,
    build_retrieval_query_view,
    score_bm25_from_retrieval_request,
    score_bm25_from_view,
    score_bm25_lexical_query,
    unique_lexical_query_terms,
)
from productiq.retrieval.bm25 import DEFAULT_BM25_B, DEFAULT_BM25_K1, rank_bm25_scored_candidates


def test_bm25_config_defaults() -> None:
    config = BM25Config()
    assert config.k1 == DEFAULT_BM25_K1
    assert config.b == DEFAULT_BM25_B


def test_bm25_config_custom_and_boundaries() -> None:
    assert BM25Config(k1=0.0, b=0.0).b == 0.0
    assert BM25Config(k1=2.0, b=1.0).b == 1.0


def test_bm25_config_rejects_invalid_values() -> None:
    with pytest.raises(ValidationError):
        BM25Config(k1=-0.1)
    with pytest.raises(ValidationError):
        BM25Config(b=1.5)
    with pytest.raises(ValidationError):
        BM25Config(k1=float("nan"))


def test_corpus_statistics_empty_and_nonempty() -> None:
    empty = BM25CorpusStatistics.from_index(build_inverted_lexical_index([]))
    assert empty.document_count == 0
    assert empty.average_document_length == 0.0
    assert empty.total_document_length == 0

    index = build_inverted_lexical_index(
        [
            LexicalIndexDocument(product_id="P1", lexical_text="a b"),
            LexicalIndexDocument(product_id="P2", lexical_text="a b c"),
        ]
    )
    stats = BM25CorpusStatistics.from_index(index)
    assert stats.document_count == 2
    assert stats.total_document_length == 5
    assert stats.average_document_length == 2.5


def test_bm25_idf_unseen_and_manual_value() -> None:
    assert bm25_idf(0, 0) == math.log1p(0.5 / 0.5)
    expected = math.log1p((2 - 1 + 0.5) / (1 + 0.5))
    assert bm25_idf(2, 1) == pytest.approx(expected)


def test_idf_rarer_terms_are_higher() -> None:
    rare = bm25_idf(document_count=5, document_frequency=1)
    common = bm25_idf(document_count=5, document_frequency=5)
    assert rare > common


def test_term_score_manual_calculation() -> None:
    index = build_inverted_lexical_index(
        [LexicalIndexDocument(product_id="P1", lexical_text="nike nike")]
    )
    scorer = BM25Scorer(index, config=BM25Config(k1=1.5, b=0.0))
    idf_value = scorer.idf("nike")
    tf = 2
    normalization = 1.0
    expected = idf_value * (tf * (1.5 + 1.0)) / (tf + 1.5 * normalization)
    assert scorer.score_term("nike", "P1") == pytest.approx(expected)


def test_zero_tf_gives_zero_term_contribution() -> None:
    index = build_inverted_lexical_index(
        [LexicalIndexDocument(product_id="P1", lexical_text="nike")]
    )
    scorer = BM25Scorer(index)
    assert scorer.score_term("adidas", "P1") == 0.0


def test_tf_saturation_diminishing_returns() -> None:
    index_low = build_inverted_lexical_index(
        [LexicalIndexDocument(product_id="P1", lexical_text="nike")]
    )
    index_high = build_inverted_lexical_index(
        [LexicalIndexDocument(product_id="P1", lexical_text="nike nike nike nike")]
    )
    scorer_low = BM25Scorer(index_low, config=BM25Config(k1=1.5, b=0.0))
    scorer_high = BM25Scorer(index_high, config=BM25Config(k1=1.5, b=0.0))
    assert scorer_high.score_term("nike", "P1") > scorer_low.score_term("nike", "P1")
    first_increment = scorer_low.score_term("nike", "P1")
    second_increment = scorer_high.score_term("nike", "P1") - first_increment
    assert second_increment > 0.0
    assert second_increment < first_increment


def test_length_normalization_with_b() -> None:
    index = build_inverted_lexical_index(
        [
            LexicalIndexDocument(product_id="P1", lexical_text="nike shoes"),
            LexicalIndexDocument(
                product_id="P2",
                lexical_text="nike shoes lightweight breathable mesh upper",
            ),
        ]
    )
    scorer_b0 = BM25Scorer(index, config=BM25Config(b=0.0))
    assert scorer_b0.score_term("nike", "P1") == pytest.approx(scorer_b0.score_term("nike", "P2"))

    scorer_b1 = BM25Scorer(index, config=BM25Config(b=1.0))
    assert scorer_b1.score_term("nike", "P1") > scorer_b1.score_term("nike", "P2")


def test_k1_zero_term_contribution_equals_idf_when_tf_positive() -> None:
    index = build_inverted_lexical_index(
        [LexicalIndexDocument(product_id="P1", lexical_text="nike nike")]
    )
    scorer = BM25Scorer(index, config=BM25Config(k1=0.0, b=0.75))
    assert scorer.score_term("nike", "P1") == pytest.approx(scorer.idf("nike"))


def test_unique_query_terms_and_duplicate_handling() -> None:
    assert unique_lexical_query_terms("nike nike shoes") == ("nike", "shoes")
    index = build_inverted_lexical_index(
        [LexicalIndexDocument(product_id="P1", lexical_text="nike shoes")]
    )
    scorer = BM25Scorer(index)
    once = scorer.score_document(("nike", "shoes"), "P1")
    duplicated = scorer.score_document(("nike", "nike", "shoes"), "P1")
    assert once == duplicated


def test_empty_query_and_unknown_terms() -> None:
    index = build_inverted_lexical_index(
        [LexicalIndexDocument(product_id="P1", lexical_text="nike")]
    )
    scorer = BM25Scorer(index)
    assert scorer.score_lexical_query("") == ()
    assert scorer.score_lexical_query("zztop") == ()


def test_unknown_terms_only_on_empty_candidate_union() -> None:
    index = build_inverted_lexical_index(
        [LexicalIndexDocument(product_id="P1", lexical_text="nike")]
    )
    assert score_bm25_lexical_query(index, "zztop qwerty") == ()


def test_query_scoring_and_ranking() -> None:
    index = build_inverted_lexical_index(
        [
            LexicalIndexDocument(product_id="P1", lexical_text="Nike black running shoes"),
            LexicalIndexDocument(product_id="P2", lexical_text="Nike black shoes"),
            LexicalIndexDocument(product_id="P3", lexical_text="Adidas running shoes"),
            LexicalIndexDocument(product_id="P4", lexical_text="Nike formal black shirt"),
        ]
    )
    ranked = score_bm25_lexical_query(index, "black Nike running shoes")
    scores = [candidate.score for candidate in ranked]
    assert scores == sorted(scores, reverse=True)
    for left, right in pairwise(ranked):
        if left.score == right.score:
            assert left.product_id < right.product_id
    assert all(math.isfinite(candidate.score) for candidate in ranked)


def test_ranking_tie_breaks_by_product_id() -> None:
    tied = (
        BM25ScoredCandidate(product_id="P2", score=1.0),
        BM25ScoredCandidate(product_id="P1", score=1.0),
    )
    ranked = rank_bm25_scored_candidates(tied)
    assert [candidate.product_id for candidate in ranked] == ["P1", "P2"]


def test_top_k_behavior() -> None:
    index = build_inverted_lexical_index(
        [
            LexicalIndexDocument(product_id="P1", lexical_text="nike black"),
            LexicalIndexDocument(product_id="P2", lexical_text="nike shoes"),
        ]
    )
    top_one = score_bm25_lexical_query(index, "nike", top_k=1)
    assert len(top_one) == 1
    with pytest.raises(LexicalRetrievalError):
        apply_bm25_top_k(top_one, top_k=0)


def test_retrieval_query_view_uses_lexical_only() -> None:
    index = build_inverted_lexical_index(
        [LexicalIndexDocument(product_id="P1", lexical_text="nike shoes")]
    )
    query = build_query_representation(
        "nike",
        lexical_text="nike shoes",
        semantic_text="completely different semantic intent",
    )
    view = build_retrieval_query_view(query)
    base = score_bm25_from_view(index, view)
    view_changed = build_retrieval_query_view(
        build_query_representation(
            "nike",
            lexical_text="nike shoes",
            semantic_text="another unrelated semantic payload",
        )
    )
    assert score_bm25_from_view(index, view_changed) == base


def test_retrieval_request_top_k_integration() -> None:
    index = build_inverted_lexical_index(
        [
            LexicalIndexDocument(product_id="P1", lexical_text="nike black"),
            LexicalIndexDocument(product_id="P2", lexical_text="nike shoes"),
            LexicalIndexDocument(product_id="P3", lexical_text="adidas black"),
        ]
    )
    request = RetrievalRequest(query=build_query_representation("nike black"), top_k=2)
    results = score_bm25_from_retrieval_request(index, request)
    assert len(results) <= 2


def test_empty_corpus_scores_are_zero_and_finite() -> None:
    scorer = BM25Scorer(build_inverted_lexical_index([]))
    assert scorer.score_term("nike", "P1") == 0.0
    assert scorer.score_lexical_query("nike") == ()


def test_zero_length_document_in_corpus() -> None:
    index = build_inverted_lexical_index(
        [
            LexicalIndexDocument(product_id="P1", lexical_text=""),
            LexicalIndexDocument(product_id="P2", lexical_text="nike"),
        ]
    )
    scorer = BM25Scorer(index)
    assert scorer.score_document(("nike",), "P1") == 0.0
    assert math.isfinite(scorer.score_document(("nike",), "P2"))
