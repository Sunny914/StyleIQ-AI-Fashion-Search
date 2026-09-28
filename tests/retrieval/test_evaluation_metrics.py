"""Tests for Phase 4.8 retrieval evaluation metrics."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from productiq.exceptions.base import LexicalRetrievalError
from productiq.retrieval.evaluation.dataset import LexicalEvaluationQuery
from productiq.retrieval.evaluation.metrics import (
    macro_mean,
    mean_reciprocal_rank,
    normalize_relevant_product_ids,
    normalize_retrieved_product_ids,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
    validate_positive_k,
)


def test_precision_at_k_basic() -> None:
    retrieved = ("A", "B", "C", "D")
    relevant = {"A", "C"}
    assert precision_at_k(retrieved, relevant, k=3) == pytest.approx(2 / 3)


def test_precision_at_k_no_relevant_in_top_k() -> None:
    assert precision_at_k(("X", "Y"), {"A"}, k=2) == 0.0


def test_precision_at_k_fewer_results_than_k() -> None:
    assert precision_at_k(("A", "B"), {"A", "B"}, k=10) == pytest.approx(1.0)


def test_recall_at_k_basic() -> None:
    retrieved = ("A", "B", "C")
    relevant = {"A", "B", "D"}
    assert recall_at_k(retrieved, relevant, k=2) == pytest.approx(2 / 3)


def test_recall_at_k_all_relevant_retrieved() -> None:
    assert recall_at_k(("A", "B"), {"A", "B"}, k=2) == pytest.approx(1.0)


def test_recall_at_k_partial() -> None:
    assert recall_at_k(("A", "X"), {"A", "B", "C"}, k=5) == pytest.approx(1 / 3)


def test_recall_at_k_empty_relevance_set() -> None:
    assert recall_at_k(("A",), {"A"}, k=1) is not None
    assert recall_at_k(("A",), set(), k=1) is None


def test_mrr_rank_one() -> None:
    rr, rank = reciprocal_rank(("A", "B"), {"A"})
    assert rr == pytest.approx(1.0)
    assert rank == 1


def test_mrr_rank_two() -> None:
    rr, rank = reciprocal_rank(("X", "A"), {"A"})
    assert rr == pytest.approx(0.5)
    assert rank == 2


def test_mrr_later_rank() -> None:
    rr, rank = reciprocal_rank(("X", "Y", "A"), {"A"})
    assert rr == pytest.approx(1 / 3)
    assert rank == 3


def test_mrr_no_relevant() -> None:
    rr, rank = reciprocal_rank(("X", "Y"), {"A"})
    assert rr == 0.0
    assert rank is None


def test_mean_reciprocal_rank_aggregation() -> None:
    assert mean_reciprocal_rank((1.0, 0.5, 0.0)) == pytest.approx(0.5)


def test_duplicate_relevance_ids_normalized() -> None:
    relevant = normalize_relevant_product_ids(("A", "A", "B"))
    assert relevant == frozenset({"A", "B"})
    assert recall_at_k(("A",), ("A", "A"), k=1) == pytest.approx(1.0)


def test_duplicate_retrieved_ids_deduped_for_ranking() -> None:
    rr, rank = reciprocal_rank(("A", "A", "B"), {"B"})
    assert rank == 2
    assert rr == pytest.approx(0.5)


def test_invalid_k_raises() -> None:
    with pytest.raises(LexicalRetrievalError):
        validate_positive_k(0)
    with pytest.raises(LexicalRetrievalError):
        precision_at_k((), set(), k=-1)


def test_empty_retrieved_product_id_raises() -> None:
    with pytest.raises(LexicalRetrievalError):
        normalize_retrieved_product_ids((" ",))


def test_empty_relevant_product_id_raises() -> None:
    with pytest.raises(LexicalRetrievalError):
        normalize_relevant_product_ids([""])


def test_evaluation_query_rejects_empty_query_id() -> None:
    with pytest.raises(ValidationError):
        LexicalEvaluationQuery(
            query_id="",
            query_text="test",
            category="cat",
            relevant_product_ids=("A",),
        )


def test_evaluation_query_rejects_empty_query_text() -> None:
    with pytest.raises(ValidationError):
        LexicalEvaluationQuery(
            query_id="q1",
            query_text="   ",
            category="cat",
            relevant_product_ids=("A",),
        )


def test_evaluation_query_rejects_empty_relevant_product_ids() -> None:
    with pytest.raises(ValidationError):
        LexicalEvaluationQuery(
            query_id="q1",
            query_text="test",
            category="cat",
            relevant_product_ids=[],
        )


def test_macro_mean_deterministic() -> None:
    assert macro_mean((0.2, 0.4, 0.6)) == pytest.approx(0.4)
    assert macro_mean((0.2, 0.4, 0.6)) == macro_mean((0.2, 0.4, 0.6))
