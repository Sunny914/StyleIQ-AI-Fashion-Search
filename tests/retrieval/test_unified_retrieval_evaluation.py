"""Tests for Phase 4.18 unified retrieval evaluation framework."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from productiq.retrieval.evaluation.dataset import LexicalEvaluationQuery, LexicalRetrievalBenchmark
from productiq.retrieval.evaluation.metrics import (
    macro_mean,
    mean_reciprocal_rank,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
)
from productiq.retrieval.evaluation.unified_comparison import compare_evaluation_results
from productiq.retrieval.evaluation.unified_evaluation_schema import (
    EvaluationLineage,
    EvaluationRequest,
)
from productiq.retrieval.evaluation.unified_evaluator import (
    UnifiedRetrievalEvaluator,
    aggregate_by_category,
    aggregate_query_results,
    build_evaluation_result,
    evaluate_single_query,
)
from productiq.retrieval.evaluation.unified_reporting import (
    build_catalog_from_evaluation_dir,
    evaluate_bm25_from_artifact,
)


def _benchmark(*queries: LexicalEvaluationQuery) -> LexicalRetrievalBenchmark:
    return LexicalRetrievalBenchmark(
        benchmark_name="test_benchmark",
        benchmark_version="1.0.0",
        catalog_artifact="resources/processed/product_representations.parquet",
        methodology="test",
        limitations="incomplete judgments in test",
        queries=queries,
    )


def _query(
    query_id: str = "q1",
    relevant: tuple[str, ...] = ("R1",),
    category: str = "brand_product",
) -> LexicalEvaluationQuery:
    return LexicalEvaluationQuery(
        query_id=query_id,
        query_text="test",
        category=category,
        relevant_product_ids=relevant,
    )


def _lineage(system_name: str = "test", **overrides: object) -> EvaluationLineage:
    base: dict[str, object] = {
        "benchmark_name": "test_benchmark",
        "benchmark_version": "1.0.0",
        "system_name": system_name,
        "retrieval_top_k": 50,
        "k_values": (1, 5, 10, 20, 50),
        "evaluation_mode": "artifact",
        "limitations": ("incomplete",),
    }
    base.update(overrides)
    return EvaluationLineage(**base)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("k", "expected_precision"),
    [(1, 1.0), (5, 2 / 3), (10, 2 / 3), (20, 2 / 3), (50, 2 / 3)],
)
def test_precision_at_k_definition(k: int, expected_precision: float) -> None:
    retrieved = ("R1", "X", "R2")
    relevant = ("R1", "R2")
    assert precision_at_k(retrieved, relevant, k=k) == pytest.approx(expected_precision)


@pytest.mark.parametrize(
    ("k", "expected_recall"),
    [(1, 1 / 3), (5, 2 / 3), (10, 2 / 3), (20, 2 / 3), (50, 2 / 3)],
)
def test_recall_at_k_definition(k: int, expected_recall: float) -> None:
    retrieved = ("R1", "X", "R2")
    relevant = ("R1", "R2", "R3")
    assert recall_at_k(retrieved, relevant, k=k) == pytest.approx(expected_recall)


def test_mrr_first_hit() -> None:
    rr, rank = reciprocal_rank(("X", "R1"), ("R1",))
    assert rr == pytest.approx(0.5)
    assert rank == 2


def test_mrr_no_relevant() -> None:
    rr, rank = reciprocal_rank(("X", "Y"), ("R1",))
    assert rr == 0.0
    assert rank is None


def test_empty_retrieval_precision_recall() -> None:
    assert precision_at_k((), ("R1",), k=10) == 0.0
    assert recall_at_k((), ("R1",), k=10) == pytest.approx(0.0)


def test_shorter_retrieval_than_k() -> None:
    assert precision_at_k(("R1",), ("R1",), k=50) == pytest.approx(1.0)


def test_all_retrieved_relevant() -> None:
    assert precision_at_k(("R1", "R2"), ("R1", "R2"), k=5) == pytest.approx(1.0)


def test_duplicate_retrieved_ids_deduped() -> None:
    row = evaluate_single_query(
        _query(relevant=("R1",)),
        ("R1", "R1", "X"),
        retrieval_top_k=50,
        k_values=(1, 5, 10, 20, 50),
    )
    assert row.metrics.retrieved_product_ids == ("R1", "X")


K_VALUES_FULL = (1, 5, 10, 20, 50)


def test_zero_judged_relevant_recall_excluded_from_macro() -> None:
    q_with = evaluate_single_query(
        _query("q1", ("R1",)),
        ("R1",),
        retrieval_top_k=50,
        k_values=K_VALUES_FULL,
    )
    metrics = aggregate_query_results((q_with,), k_values=K_VALUES_FULL)
    assert metrics.recall_aggregate_query_count == 1


def test_macro_aggregation() -> None:
    q1 = evaluate_single_query(_query("q1"), ("R1",), retrieval_top_k=50, k_values=(1, 5))
    q2 = evaluate_single_query(_query("q2"), ("X",), retrieval_top_k=50, k_values=(1, 5))
    agg = aggregate_query_results((q1, q2), k_values=(1, 5))
    assert agg.mrr == pytest.approx(mean_reciprocal_rank((1.0, 0.0)))
    assert agg.mean_precision_at_k[1] == pytest.approx(
        macro_mean((q1.metrics.precision_at_k[1], q2.metrics.precision_at_k[1]))
    )


def test_category_aggregation() -> None:
    q1 = evaluate_single_query(
        _query("q1", category="brand_color"),
        ("R1",),
        retrieval_top_k=50,
        k_values=(10,),
    )
    q2 = evaluate_single_query(
        _query("q2", category="brand_activity"),
        ("R1",),
        retrieval_top_k=50,
        k_values=(10,),
    )
    categories = aggregate_by_category((q1, q2), k_values=(10,))
    assert [row.category for row in categories] == ["brand_activity", "brand_color"]


def test_compare_compatible_runs() -> None:
    benchmark = _benchmark(_query())
    row = evaluate_single_query(_query(), ("R1",), retrieval_top_k=50, k_values=K_VALUES_FULL)
    left = build_evaluation_result(
        benchmark=benchmark,
        per_query=(row,),
        lineage=_lineage("a"),
    )
    right = build_evaluation_result(
        benchmark=benchmark,
        per_query=(row,),
        lineage=_lineage("b"),
    )
    comparison = compare_evaluation_results(left, right)
    assert comparison.compatible
    assert comparison.mrr_delta.absolute_delta == pytest.approx(0.0)


def test_compare_incompatible_benchmark_version() -> None:
    benchmark = _benchmark(_query())
    row = evaluate_single_query(_query(), ("R1",), retrieval_top_k=50, k_values=K_VALUES_FULL)
    left = build_evaluation_result(
        benchmark=benchmark,
        per_query=(row,),
        lineage=_lineage("a", benchmark_version="1.0.0"),
    )
    right = build_evaluation_result(
        benchmark=benchmark,
        per_query=(row,),
        lineage=_lineage("b", benchmark_version="2.0.0"),
    )
    comparison = compare_evaluation_results(left, right)
    assert not comparison.compatible
    assert comparison.incompatibility_reasons


def test_compare_absolute_and_relative_delta() -> None:
    benchmark = _benchmark(_query("q1"), _query("q2", relevant=("R1", "R2")))
    row1 = evaluate_single_query(_query("q1"), ("R1",), retrieval_top_k=50, k_values=K_VALUES_FULL)
    row2_miss = evaluate_single_query(
        _query("q2", relevant=("R1", "R2")),
        ("X",),
        retrieval_top_k=50,
        k_values=K_VALUES_FULL,
    )
    row2_hit = evaluate_single_query(
        _query("q2", relevant=("R1", "R2")),
        ("R1",),
        retrieval_top_k=50,
        k_values=K_VALUES_FULL,
    )
    baseline = build_evaluation_result(
        benchmark=benchmark,
        per_query=(row1, row2_miss),
        lineage=_lineage("baseline"),
    )
    improved = build_evaluation_result(
        benchmark=benchmark,
        per_query=(row1, row2_hit),
        lineage=_lineage("comparison"),
    )
    comparison = compare_evaluation_results(baseline, improved)
    assert comparison.compatible
    assert comparison.mrr_delta.absolute_delta == pytest.approx(0.5)
    assert comparison.precision_at_k_deltas[10].relative_delta is not None


def test_lineage_does_not_fabricate_embedding_fields() -> None:
    lineage = _lineage("bm25")
    assert lineage.embedding_model_id is None


def test_deterministic_query_ordering() -> None:
    benchmark = _benchmark(_query("q_b"), _query("q_a"))
    rows = (
        evaluate_single_query(_query("q_b"), ("R1",), retrieval_top_k=50, k_values=K_VALUES_FULL),
        evaluate_single_query(_query("q_a"), ("R1",), retrieval_top_k=50, k_values=K_VALUES_FULL),
    )
    result = build_evaluation_result(
        benchmark=benchmark, per_query=rows, lineage=_lineage("x")
    )
    assert [row.query_id for row in result.per_query] == ["q_a", "q_b"]


def test_bm25_artifact_matches_official_aggregate() -> None:
    eval_dir = Path("resources/evaluation")
    if not (eval_dir / "lexical_retrieval_benchmark_v1_run.json").is_file():
        pytest.skip("lexical run artifact missing")
    official = json.loads((eval_dir / "lexical_retrieval_benchmark_v1_run.json").read_text())
    result = evaluate_bm25_from_artifact(
        eval_dir, eval_dir / "lexical_retrieval_benchmark_v1.json"
    )
    assert result.aggregate.mrr == pytest.approx(official["aggregate"]["mrr"])
    assert result.aggregate.mean_precision_at_k[10] == pytest.approx(
        official["aggregate"]["mean_precision_at_k"]["10"]
        if isinstance(official["aggregate"]["mean_precision_at_k"], dict)
        and "10" in official["aggregate"]["mean_precision_at_k"]
        else official["aggregate"]["mean_precision_at_k"][10]
    )


def test_catalog_from_artifacts() -> None:
    eval_dir = Path("resources/evaluation")
    if not (eval_dir / "hybrid_rrf_benchmark_v1_run.json").is_file():
        pytest.skip("benchmark artifacts missing")
    catalog = build_catalog_from_evaluation_dir(eval_dir)
    assert catalog.query_count == 10
    assert len(catalog.evaluations) == 3
    assert len(catalog.comparisons) == 3


def test_unified_evaluator_live_stub() -> None:
    class StubRetriever:
        def retrieve(self, request):
            from productiq.retrieval.contracts import (
                RetrievalCandidate,
                RetrievalMethod,
                RetrievalResponse,
            )

            return RetrievalResponse(
                candidates=(
                    RetrievalCandidate(
                        product_id="R1",
                        score=1.0,
                        method=RetrievalMethod.BM25,
                    ),
                )
            )

    benchmark = _benchmark(_query())
    evaluator = UnifiedRetrievalEvaluator(
        EvaluationRequest(system_name="stub", retrieval_top_k=50, k_values=(10,))
    )
    result = evaluator.evaluate(benchmark, StubRetriever())
    assert result.per_query[0].reciprocal_rank == pytest.approx(1.0)
