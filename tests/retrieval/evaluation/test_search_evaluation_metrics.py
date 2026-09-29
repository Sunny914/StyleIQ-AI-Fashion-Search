"""Tests for Phase 12.3 search evaluation metrics."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest
from pydantic import ValidationError

from productiq.exceptions import RetrievalError
from productiq.recommendation.evaluation.metrics import ndcg_at_k
from productiq.retrieval.evaluation.search_evaluation import (
    SEARCH_BENCHMARK_FILENAME,
    SearchEvaluationBenchmark,
    SearchEvaluationBenchmarkMetadata,
    SearchEvaluationQuery,
    SearchEvaluationVariant,
    SearchMetricConfiguration,
    SearchRankedResultsForQuery,
    SearchRelevanceJudgment,
    aggregate_search_query_metrics,
    compute_search_query_metrics,
    evaluate_search_variant_metrics,
    load_search_evaluation_benchmark,
    search_variant_evaluation_result_to_dict,
    validate_search_ranked_product_ids,
)


def _metadata() -> SearchEvaluationBenchmarkMetadata:
    return SearchEvaluationBenchmarkMetadata(
        benchmark_name="metrics_test",
        benchmark_version="1.0.0",
        methodology="test",
        labeling_methodology="test",
        limitations="test",
    )


def _graded_query() -> SearchEvaluationQuery:
    return SearchEvaluationQuery(
        query_id="q_graded",
        query_text="graded demo",
        query_category="demo",
        relevance_judgments=(
            SearchRelevanceJudgment(product_id="A", grade=3),
            SearchRelevanceJudgment(product_id="B", grade=2),
            SearchRelevanceJudgment(product_id="C", grade=1),
            SearchRelevanceJudgment(product_id="D", grade=0),
        ),
    )


def _config(*, k_values: tuple[int, ...] = (1, 5), evaluation_top_k: int = 5) -> SearchMetricConfiguration:
    return SearchMetricConfiguration(
        k_values=k_values,
        evaluation_top_k=evaluation_top_k,
        min_relevant_grade=2,
        compute_ndcg=True,
    )


class TestGradedHandVerification:
    """Ranking X, A, Y, B, Z with grades A=3, B=2, C=1, D=0; min_relevant_grade=2."""

    RANKING = ("X", "A", "Y", "B", "Z")

    def test_precision_recall_hit_mrr_at_five(self) -> None:
        metrics = compute_search_query_metrics(_graded_query(), self.RANKING, _config())
        assert metrics.precision_at_k[5] == pytest.approx(0.4)
        assert metrics.recall_at_k[5] == pytest.approx(1.0)
        assert metrics.hit_rate_at_k[5] == pytest.approx(1.0)
        assert metrics.reciprocal_rank == pytest.approx(0.5)
        assert metrics.judged_relevant_count == 2
        assert metrics.recall_aggregate_eligible is True

    def test_at_k_one(self) -> None:
        metrics = compute_search_query_metrics(_graded_query(), self.RANKING, _config())
        assert metrics.precision_at_k[1] == pytest.approx(0.0)
        assert metrics.recall_at_k[1] == pytest.approx(0.0)
        assert metrics.hit_rate_at_k[1] == pytest.approx(0.0)

    def test_ndcg_at_five_matches_primitive(self) -> None:
        grades = {"A": 3, "B": 2, "C": 1, "D": 0}
        expected = ndcg_at_k(self.RANKING, grades, k=5)
        metrics = compute_search_query_metrics(_graded_query(), self.RANKING, _config())
        assert metrics.ndcg_at_k[5] == pytest.approx(expected)

    def test_ndcg_manual_dcg_ratio(self) -> None:
        grades = {"A": 3, "B": 2, "C": 1, "D": 0}
        prefix = self.RANKING[:5]
        gain_list = [float(grades.get(product_id, 0)) for product_id in prefix]
        ideal = sorted(grades.values(), reverse=True)[:5]
        dcg = gain_list[0] + sum(
            gain / math.log2(index + 1) for index, gain in enumerate(gain_list[1:], start=2)
        )
        idcg = ideal[0] + sum(
            gain / math.log2(index + 1) for index, gain in enumerate(ideal[1:], start=2)
        )
        metrics = compute_search_query_metrics(_graded_query(), self.RANKING, _config())
        assert metrics.ndcg_at_k[5] == pytest.approx(dcg / idcg)


class TestEdgeCases:
    def test_empty_ranked_results(self) -> None:
        metrics = compute_search_query_metrics(_graded_query(), (), _config())
        assert metrics.precision_at_k[5] == pytest.approx(0.0)
        assert metrics.recall_at_k[5] == pytest.approx(0.0)
        assert metrics.hit_rate_at_k[5] == pytest.approx(0.0)
        assert metrics.reciprocal_rank == pytest.approx(0.0)
        assert metrics.ndcg_at_k[5] == pytest.approx(0.0)

    def test_no_relevant_judgments_for_binary_metrics(self) -> None:
        query = SearchEvaluationQuery(
            query_id="q_low",
            query_text="low grades",
            relevance_judgments=(SearchRelevanceJudgment(product_id="C", grade=1),),
        )
        metrics = compute_search_query_metrics(query, ("C", "X"), _config())
        assert metrics.judged_relevant_count == 0
        assert metrics.recall_aggregate_eligible is False
        assert metrics.recall_at_k[5] is None
        assert metrics.hit_rate_at_k[5] == pytest.approx(0.0)

    def test_relevant_at_rank_one(self) -> None:
        query = SearchEvaluationQuery(
            query_id="q1",
            query_text="t",
            relevance_judgments=(SearchRelevanceJudgment(product_id="A", grade=3),),
        )
        metrics = compute_search_query_metrics(query, ("A", "B"), _config(k_values=(1, 2)))
        assert metrics.reciprocal_rank == pytest.approx(1.0)
        assert metrics.precision_at_k[1] == pytest.approx(1.0)
        assert metrics.hit_rate_at_k[1] == pytest.approx(1.0)

    def test_k_larger_than_returned_results(self) -> None:
        query = SearchEvaluationQuery(
            query_id="q1",
            query_text="t",
            relevance_judgments=(
                SearchRelevanceJudgment(product_id="A", grade=2),
                SearchRelevanceJudgment(product_id="B", grade=2),
            ),
        )
        metrics = compute_search_query_metrics(
            query,
            ("A",),
            SearchMetricConfiguration(k_values=(10,), evaluation_top_k=10, min_relevant_grade=2),
        )
        assert metrics.precision_at_k[10] == pytest.approx(1.0)
        assert metrics.recall_at_k[10] == pytest.approx(0.5)

    def test_evaluation_top_k_truncates_prefix(self) -> None:
        query = SearchEvaluationQuery(
            query_id="q1",
            query_text="t",
            relevance_judgments=(SearchRelevanceJudgment(product_id="Z", grade=2),),
        )
        ranking = ("A", "B", "C", "D", "Z")
        metrics = compute_search_query_metrics(
            query,
            ranking,
            SearchMetricConfiguration(k_values=(5,), evaluation_top_k=3, min_relevant_grade=2),
        )
        assert metrics.ranked_product_ids == ("A", "B", "C")
        assert metrics.recall_at_k[5] == pytest.approx(0.0)

    def test_duplicate_ranked_ids_rejected(self) -> None:
        with pytest.raises(RetrievalError, match="duplicate ranked"):
            validate_search_ranked_product_ids(("A", "A"))

    def test_duplicate_in_result_contract(self) -> None:
        with pytest.raises(ValidationError, match="duplicate ranked"):
            SearchRankedResultsForQuery(query_id="q1", ranked_product_ids=("A", "A"))

    def test_compute_ndcg_disabled(self) -> None:
        config = SearchMetricConfiguration(
            k_values=(1, 5),
            evaluation_top_k=5,
            compute_ndcg=False,
        )
        metrics = compute_search_query_metrics(_graded_query(), TestGradedHandVerification.RANKING, config)
        assert metrics.ndcg_at_k == {}


class TestMacroAggregation:
    def test_macro_means_across_queries(self) -> None:
        q1 = SearchEvaluationQuery(
            query_id="q1",
            query_text="t",
            relevance_judgments=(SearchRelevanceJudgment(product_id="A", grade=2),),
        )
        q2 = SearchEvaluationQuery(
            query_id="q2",
            query_text="t",
            relevance_judgments=(SearchRelevanceJudgment(product_id="B", grade=2),),
        )
        config = _config(k_values=(1,))
        row1 = compute_search_query_metrics(q1, ("A",), config)
        row2 = compute_search_query_metrics(q2, ("X",), config)
        aggregate = aggregate_search_query_metrics((row1, row2), config)
        assert aggregate.query_count == 2
        assert aggregate.mean_precision_at_k[1] == pytest.approx(0.5)
        assert aggregate.mean_hit_rate_at_k[1] == pytest.approx(0.5)
        assert aggregate.mrr == pytest.approx(0.5)

    def test_recall_aggregate_skips_ineligible_queries(self) -> None:
        eligible = compute_search_query_metrics(
            SearchEvaluationQuery(
                query_id="q1",
                query_text="t",
                relevance_judgments=(SearchRelevanceJudgment(product_id="A", grade=2),),
            ),
            ("A",),
            _config(k_values=(1,)),
        )
        ineligible = compute_search_query_metrics(
            SearchEvaluationQuery(
                query_id="q2",
                query_text="t",
                relevance_judgments=(SearchRelevanceJudgment(product_id="C", grade=1),),
            ),
            ("C",),
            _config(k_values=(1,)),
        )
        aggregate = aggregate_search_query_metrics((eligible, ineligible), _config(k_values=(1,)))
        assert aggregate.recall_aggregate_query_count == 1
        assert aggregate.mean_recall_at_k[1] == pytest.approx(1.0)


class TestVariantEvaluation:
    def test_evaluate_search_variant_metrics_on_repository_benchmark(self) -> None:
        path = Path("resources/evaluation") / SEARCH_BENCHMARK_FILENAME
        benchmark = load_search_evaluation_benchmark(path)
        ranked = tuple(
            SearchRankedResultsForQuery(
                query_id=query.query_id,
                ranked_product_ids=tuple(
                    judgment.product_id for judgment in query.relevance_judgments[:2]
                ),
            )
            for query in benchmark.queries
        )
        variant = SearchEvaluationVariant(variant_name="synthetic", variant_version="0.0.0")
        result = evaluate_search_variant_metrics(benchmark, variant, ranked)
        assert len(result.per_query) == len(benchmark.queries)
        assert result.aggregate.query_count == len(benchmark.queries)

    def test_missing_query_rankings_raises(self) -> None:
        benchmark = SearchEvaluationBenchmark(
            metadata=_metadata(),
            queries=(
                SearchEvaluationQuery(
                    query_id="q1",
                    query_text="t",
                    relevance_judgments=(SearchRelevanceJudgment(product_id="A", grade=2),),
                ),
            ),
        )
        with pytest.raises(RetrievalError, match="missing ranked results"):
            evaluate_search_variant_metrics(
                benchmark,
                SearchEvaluationVariant(variant_name="v", variant_version="1"),
                (),
            )

    def test_deterministic_serialization(self) -> None:
        benchmark = SearchEvaluationBenchmark(
            metadata=_metadata(),
            queries=(_graded_query(),),
        )
        ranked = (
            SearchRankedResultsForQuery(
                query_id="q_graded",
                ranked_product_ids=TestGradedHandVerification.RANKING,
            ),
        )
        variant = SearchEvaluationVariant(variant_name="v", variant_version="1")
        first = evaluate_search_variant_metrics(benchmark, variant, ranked)
        second = evaluate_search_variant_metrics(benchmark, variant, ranked)
        assert json.dumps(search_variant_evaluation_result_to_dict(first), sort_keys=True) == json.dumps(
            search_variant_evaluation_result_to_dict(second),
            sort_keys=True,
        )
