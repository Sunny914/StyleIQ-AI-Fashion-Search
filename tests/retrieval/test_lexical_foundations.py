"""Tests for Phase 4.4 lexical retrieval foundations."""

from __future__ import annotations

import inspect

import pytest
from pydantic import ValidationError

from productiq.exceptions.base import LexicalRetrievalError
from productiq.representation.query_contract import build_query_representation
from productiq.retrieval import (
    InvertedLexicalIndex,
    LexicalIndexDocument,
    LexicalPosting,
    build_inverted_lexical_index,
    build_retrieval_query_view,
    retrieve_lexical_candidates,
    retrieve_lexical_candidates_from_view,
    tokenize_lexical_text,
)
from productiq.retrieval.lexical import normalize_lexical_surface_text


def test_tokenize_normal_text_and_whitespace() -> None:
    assert tokenize_lexical_text(" Nike Black Running Shoes ") == (
        "nike",
        "black",
        "running",
        "shoes",
    )


def test_tokenize_repeated_whitespace() -> None:
    assert tokenize_lexical_text("nike   black") == ("nike", "black")


def test_tokenize_blank_and_none() -> None:
    assert tokenize_lexical_text("") == ()
    assert tokenize_lexical_text("   ") == ()
    assert tokenize_lexical_text(None) == ()


def test_tokenize_is_deterministic() -> None:
    text = "Adidas black running shoes"
    assert tokenize_lexical_text(text) == tokenize_lexical_text(text)


def test_surface_normalization_matches_whitespace_rules() -> None:
    assert normalize_lexical_surface_text("  a   b  ") == "a b"


def test_term_frequency_in_document() -> None:
    tokens = tokenize_lexical_text("nike nike running shoes")
    assert tokens.count("nike") == 2
    assert tokens.count("running") == 1
    assert tokens.count("shoes") == 1


def _df_index() -> InvertedLexicalIndex:
    return build_inverted_lexical_index(
        [
            LexicalIndexDocument(product_id="P1", lexical_text="nike shoes"),
            LexicalIndexDocument(product_id="P2", lexical_text="nike running shoes"),
            LexicalIndexDocument(product_id="P3", lexical_text="adidas shoes"),
        ]
    )


def test_document_frequency_examples() -> None:
    index = _df_index()
    assert index.document_frequency("nike") == 2
    assert index.document_frequency("shoes") == 3
    assert index.document_frequency("adidas") == 1
    assert index.document_frequency("missing") == 0


def test_document_length_is_token_count() -> None:
    index = build_inverted_lexical_index(
        [
            LexicalIndexDocument(
                product_id="P1",
                lexical_text="nike black running shoes",
            ),
            LexicalIndexDocument(
                product_id="P2",
                lexical_text="nike black running shoes lightweight breathable",
            ),
        ]
    )
    assert index.document_length("P1") == 4
    assert index.document_length("P2") == 6


def test_inverted_index_postings() -> None:
    index = build_inverted_lexical_index(
        [
            LexicalIndexDocument(product_id="P1", lexical_text="nike black running shoes"),
            LexicalIndexDocument(product_id="P2", lexical_text="adidas black running shoes"),
            LexicalIndexDocument(product_id="P3", lexical_text="nike white casual shoes"),
        ]
    )
    assert [p.product_id for p in index.lookup_term("nike")] == ["P1", "P3"]
    assert [p.product_id for p in index.lookup_term("black")] == ["P1", "P2"]
    assert [p.product_id for p in index.lookup_term("running")] == ["P1", "P2"]
    assert [p.product_id for p in index.lookup_term("shoes")] == ["P1", "P2", "P3"]


def test_posting_term_frequencies_and_ordering() -> None:
    index = build_inverted_lexical_index(
        [LexicalIndexDocument(product_id="P1", lexical_text="nike nike running shoes")]
    )
    postings = index.lookup_term("nike")
    assert postings == (LexicalPosting(product_id="P1", term_frequency=2),)
    assert index.term_frequency("nike", "P1") == 2
    assert index.term_frequency("running", "P1") == 1


def test_unknown_term_lookup_returns_empty_postings() -> None:
    index = _df_index()
    assert index.lookup_term("unknown") == ()


def test_candidate_retrieval_union_without_ranking() -> None:
    index = build_inverted_lexical_index(
        [
            LexicalIndexDocument(product_id="P1", lexical_text="Nike black running shoes"),
            LexicalIndexDocument(product_id="P2", lexical_text="Adidas black running shoes"),
            LexicalIndexDocument(product_id="P3", lexical_text="Nike white casual shoes"),
        ]
    )
    candidates = retrieve_lexical_candidates(index, "black Nike shoes")
    assert candidates == ("P1", "P2", "P3")


def test_candidate_retrieval_from_retrieval_query_view() -> None:
    index = build_inverted_lexical_index(
        [
            LexicalIndexDocument(product_id="P1", lexical_text="nike black running shoes"),
            LexicalIndexDocument(product_id="P2", lexical_text="adidas black running shoes"),
            LexicalIndexDocument(product_id="P3", lexical_text="nike white casual shoes"),
        ]
    )
    query = build_query_representation(
        "black nike shoes",
        lexical_text="black Nike shoes",
    )
    view = build_retrieval_query_view(query)
    assert retrieve_lexical_candidates_from_view(index, view) == ("P1", "P2", "P3")


def test_empty_corpus() -> None:
    index = build_inverted_lexical_index([])
    assert index.total_document_count() == 0
    assert retrieve_lexical_candidates(index, "nike") == ()


def test_empty_document_text_has_zero_length() -> None:
    index = build_inverted_lexical_index([LexicalIndexDocument(product_id="P1", lexical_text="")])
    assert index.document_length("P1") == 0
    assert index.document_frequency("nike") == 0


def test_query_only_unknown_terms() -> None:
    index = _df_index()
    assert retrieve_lexical_candidates(index, "zztop qwerty") == ()


def test_duplicate_product_id_rejected() -> None:
    with pytest.raises(LexicalRetrievalError):
        build_inverted_lexical_index(
            [
                LexicalIndexDocument(product_id="P1", lexical_text="nike"),
                LexicalIndexDocument(product_id="P1", lexical_text="adidas"),
            ]
        )


def test_empty_product_id_rejected() -> None:
    with pytest.raises(ValueError):
        LexicalIndexDocument(product_id="  ", lexical_text="nike")


def test_index_rebuild_is_deterministic() -> None:
    documents = [
        LexicalIndexDocument(product_id="P2", lexical_text="black shoes"),
        LexicalIndexDocument(product_id="P1", lexical_text="nike shoes"),
    ]
    first = build_inverted_lexical_index(documents)
    second = build_inverted_lexical_index(documents)
    assert first == second


def test_inverted_index_is_frozen() -> None:
    index = _df_index()
    with pytest.raises(ValidationError):
        index.document_ids = ()  # type: ignore[misc]


def test_total_document_count() -> None:
    assert _df_index().total_document_count() == 3


def test_lexical_module_does_not_implement_bm25_or_vector_search() -> None:
    from productiq.retrieval import lexical

    source = inspect.getsource(lexical).lower()
    for token in ("bm25", "tf-idf", "tfidf", "idf(", "pgvector", "faiss", "embedding"):
        assert token not in source
