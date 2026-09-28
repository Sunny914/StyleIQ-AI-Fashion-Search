"""Tests for Phase 4.8 lexical retrieval evaluator."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from productiq.retrieval.contracts import (
    RetrievalCandidate,
    RetrievalMethod,
    RetrievalRequest,
    RetrievalResponse,
)
from productiq.retrieval.evaluation import (
    LexicalEvaluationQuery,
    LexicalRetrievalBenchmark,
    LexicalRetrievalEvaluator,
    load_lexical_retrieval_benchmark,
    macro_mean,
)
from productiq.retrieval.evaluation.evaluator import LexicalRetrievalEvaluator as EvaluatorClass


class FakeRetriever:
    """In-memory retriever for evaluation tests (not BM25)."""

    def __init__(self, ranking: dict[str, tuple[str, ...]]) -> None:
        self._ranking = ranking

    def retrieve(self, request: RetrievalRequest) -> RetrievalResponse:
        query_text = request.query.query_text.strip().lower()
        product_ids = self._ranking.get(query_text, ())
        top = product_ids[: request.top_k]
        candidates = tuple(
            RetrievalCandidate(product_id=pid, score=float(len(top) - i), method=RetrievalMethod.BM25)
            for i, pid in enumerate(top)
        )
        return RetrievalResponse(candidates=candidates)


def _tiny_benchmark() -> LexicalRetrievalBenchmark:
    return LexicalRetrievalBenchmark(
        benchmark_name="test",
        benchmark_version="0.0.1",
        catalog_artifact="test.parquet",
        methodology="test",
        limitations="test",
        queries=(
            LexicalEvaluationQuery(
                query_id="q1",
                query_text="alpha",
                category="test",
                relevant_product_ids=("A", "B"),
            ),
            LexicalEvaluationQuery(
                query_id="q2",
                query_text="beta",
                category="test",
                relevant_product_ids=("C",),
            ),
        ),
    )


def test_evaluator_does_not_import_bm25_retriever_module() -> None:
    import productiq.retrieval.evaluation.evaluator as evaluator_module

    source = Path(evaluator_module.__file__).read_text(encoding="utf-8")
    assert "bm25_retriever" not in source
    assert "BM25Retriever" not in source


def test_evaluator_with_fake_retriever() -> None:
    retriever = FakeRetriever(
        {
            "alpha": ("A", "X", "B"),
            "beta": ("X", "Y"),
        }
    )
    evaluator = LexicalRetrievalEvaluator(retrieval_top_k=10, k_values=(1, 3))
    result = evaluator.evaluate(_tiny_benchmark(), retriever)
    assert result.aggregate.query_count == 2
    q1 = next(row for row in result.per_query if row.query_id == "q1")
    assert q1.metrics.precision_at_k[1] == pytest.approx(1.0)
    assert q1.metrics.recall_at_k[3] == pytest.approx(1.0)
    assert q1.metrics.reciprocal_rank == pytest.approx(1.0)
    q2 = next(row for row in result.per_query if row.query_id == "q2")
    assert q2.metrics.reciprocal_rank == 0.0


def test_macro_averaging_across_queries() -> None:
    retriever = FakeRetriever({"alpha": ("X",), "beta": ("C",)})
    evaluator = LexicalRetrievalEvaluator(retrieval_top_k=5, k_values=(1,))
    result = evaluator.evaluate(_tiny_benchmark(), retriever)
    expected_p1 = macro_mean((0.0, 1.0))
    assert result.aggregate.mean_precision_at_k[1] == pytest.approx(expected_p1)
    assert result.aggregate.mrr == pytest.approx(macro_mean((0.0, 1.0)))


def test_evaluator_deterministic_aggregate() -> None:
    retriever = FakeRetriever({"alpha": ("A", "B"), "beta": ("C",)})
    evaluator = LexicalRetrievalEvaluator(retrieval_top_k=5, k_values=(1, 2))
    first = evaluator.evaluate(_tiny_benchmark(), retriever)
    second = evaluator.evaluate(_tiny_benchmark(), retriever)
    assert first.aggregate.model_dump() == second.aggregate.model_dump()


def test_benchmark_json_loads() -> None:
    path = Path("resources/evaluation/lexical_retrieval_benchmark_v1.json")
    benchmark = load_lexical_retrieval_benchmark(path)
    assert len(benchmark.queries) == 10
    assert benchmark.benchmark_version == "1.0.0"


def test_bm25_scoped_benchmark_evaluation() -> None:
    """Real BM25 on a benchmark-scoped catalog slice (fast, no full index load)."""
    from productiq.retrieval.evaluation import build_benchmark_scoped_bm25_retriever

    parquet_path = Path("resources/processed/product_representations.parquet")
    if not parquet_path.is_file():
        pytest.skip("representation parquet not present")
    benchmark = load_lexical_retrieval_benchmark(
        Path("resources/evaluation/lexical_retrieval_benchmark_v1.json")
    )
    retriever, doc_count = build_benchmark_scoped_bm25_retriever(
        parquet_path,
        benchmark,
        max_docs_per_term=200,
        max_total_docs=2_000,
    )
    assert doc_count > 0
    evaluator = LexicalRetrievalEvaluator(retrieval_top_k=50, k_values=(1, 5, 10))
    result = evaluator.evaluate(benchmark, retriever)
    assert result.aggregate.query_count == len(benchmark.queries)
    assert 0.0 <= result.aggregate.mrr <= 1.0


@pytest.mark.skipif(
    os.environ.get("PRODUCTIQ_LEXICAL_EVAL_SMOKE") != "1",
    reason="Set PRODUCTIQ_LEXICAL_EVAL_SMOKE=1 to run BM25 benchmark integration",
)
def test_bm25_benchmark_evaluation_integration() -> None:
    from productiq.retrieval import create_bm25_retriever_from_index_path
    from productiq.retrieval.evaluation import build_benchmark_scoped_bm25_retriever

    index_path = Path("resources/processed/bm25_lexical_index.pkl")
    parquet_path = Path("resources/processed/product_representations.parquet")
    benchmark = load_lexical_retrieval_benchmark(
        Path("resources/evaluation/lexical_retrieval_benchmark_v1.json")
    )
    if os.environ.get("PRODUCTIQ_LEXICAL_EVAL_SCOPED") == "1":
        retriever, _ = build_benchmark_scoped_bm25_retriever(
            parquet_path,
            benchmark,
            max_docs_per_term=500,
            max_total_docs=8_000,
        )
    elif index_path.is_file():
        try:
            retriever = create_bm25_retriever_from_index_path(index_path)
        except MemoryError:
            retriever, _ = build_benchmark_scoped_bm25_retriever(
                parquet_path,
                benchmark,
                max_docs_per_term=500,
                max_total_docs=8_000,
            )
    elif parquet_path.is_file():
        retriever, _ = build_benchmark_scoped_bm25_retriever(
            parquet_path,
            benchmark,
            max_docs_per_term=500,
            max_total_docs=8_000,
        )
    else:
        pytest.skip("need persisted index or representation parquet for BM25 evaluation")
    evaluator = LexicalRetrievalEvaluator(retrieval_top_k=50, k_values=(1, 5, 10, 20, 50))
    result = evaluator.evaluate(benchmark, retriever)
    if os.environ.get("PRODUCTIQ_LEXICAL_EVAL_PRINT") == "1":
        import json

        print(json.dumps(result.aggregate.model_dump(mode="json"), indent=2))
    assert result.aggregate.recall_aggregate_query_count == len(benchmark.queries)
    assert 0.0 <= result.aggregate.mrr <= 1.0
    for value in result.aggregate.mean_precision_at_k.values():
        assert 0.0 <= value <= 1.0
    assert isinstance(EvaluatorClass, type)
