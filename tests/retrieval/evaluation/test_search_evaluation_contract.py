"""Tests for Phase 12.1 search evaluation contracts."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from productiq.exceptions import LexicalRetrievalError
from productiq.retrieval.evaluation.search_evaluation import (
    SEARCH_EVALUATION_CONTRACT_VERSION,
    SearchEvaluationBenchmark,
    SearchEvaluationBenchmarkMetadata,
    SearchEvaluationQuery,
    SearchEvaluationRequest,
    SearchEvaluationVariant,
    SearchExperimentComparison,
    SearchMetricConfiguration,
    SearchQueryMetricResult,
    SearchRelevanceJudgment,
    SearchVariantEvaluationResult,
    compare_search_evaluation_variants,
    lexical_query_to_search_evaluation_query,
    search_evaluation_benchmark_to_dict,
    search_experiment_comparison_to_dict,
    search_variant_evaluation_result_to_dict,
)
from productiq.retrieval.evaluation.search_evaluation.result_schema import (
    SearchAggregateMetricResult,
    SearchEvaluationLineage,
)


def _metadata(**overrides: str) -> SearchEvaluationBenchmarkMetadata:
    base = {
        "benchmark_name": "productiq_search_eval_v1",
        "benchmark_version": "1.0.0",
        "methodology": "Curated offline search queries.",
        "labeling_methodology": "Human graded relevance 0-3.",
        "limitations": "Incomplete ground truth.",
    }
    base.update(overrides)
    return SearchEvaluationBenchmarkMetadata(**base)


def _query(query_id: str = "q1") -> SearchEvaluationQuery:
    return SearchEvaluationQuery(
        query_id=query_id,
        query_text="black nike shoes",
        query_category="brand_color",
        relevance_judgments=(
            SearchRelevanceJudgment(product_id="P1", grade=3),
            SearchRelevanceJudgment(product_id="P2", grade=2),
        ),
    )


def _benchmark() -> SearchEvaluationBenchmark:
    return SearchEvaluationBenchmark(metadata=_metadata(), queries=(_query("q1"), _query("q2")))


def _variant(name: str = "bm25_baseline") -> SearchEvaluationVariant:
    return SearchEvaluationVariant(
        variant_name=name,
        variant_version="1.0.0",
        description="Example variant",
        lineage_labels=("bm25",),
    )


def _result(
    *,
    variant_name: str,
    mrr: float,
) -> SearchVariantEvaluationResult:
    config = SearchMetricConfiguration(k_values=(1, 5), evaluation_top_k=5)
    lineage = SearchEvaluationLineage(
        benchmark_name="productiq_search_eval_v1",
        benchmark_version="1.0.0",
        variant_name=variant_name,
        variant_version="1.0.0",
        metric_configuration=config,
    )
    per_query = (
        SearchQueryMetricResult(
            query_id="q1",
            query_text="black nike shoes",
            query_category="brand_color",
            judged_relevant_count=2,
            ranked_product_ids=("P1", "P3"),
            precision_at_k={1: 1.0, 5: 0.5},
            recall_at_k={1: 0.5, 5: 0.5},
            hit_rate_at_k={1: 1.0, 5: 1.0},
            ndcg_at_k={1: 1.0, 5: 0.9},
            reciprocal_rank=1.0,
            recall_aggregate_eligible=True,
        ),
    )
    aggregate = SearchAggregateMetricResult(
        query_count=1,
        recall_aggregate_query_count=1,
        ndcg_aggregate_query_count=1,
        k_values=(1, 5),
        mean_precision_at_k={1: 1.0, 5: 0.5},
        mean_recall_at_k={1: 0.5, 5: 0.5},
        mean_hit_rate_at_k={1: 1.0, 5: 1.0},
        mean_ndcg_at_k={1: 1.0, 5: 0.9},
        mrr=mrr,
    )
    return SearchVariantEvaluationResult(lineage=lineage, per_query=per_query, aggregate=aggregate)


class TestBenchmarkContracts:
    def test_valid_benchmark(self) -> None:
        benchmark = _benchmark()
        assert len(benchmark.queries) == 2

    def test_duplicate_query_ids_rejected(self) -> None:
        with pytest.raises(ValidationError, match="unique"):
            SearchEvaluationBenchmark(metadata=_metadata(), queries=(_query("q1"), _query("q1")))

    def test_duplicate_judgment_product_ids_rejected(self) -> None:
        with pytest.raises(ValidationError, match="duplicate product_id"):
            SearchEvaluationQuery(
                query_id="q1",
                query_text="test",
                relevance_judgments=(
                    SearchRelevanceJudgment(product_id="P1", grade=2),
                    SearchRelevanceJudgment(product_id="P1", grade=3),
                ),
            )

    def test_invalid_relevance_grade(self) -> None:
        with pytest.raises(ValidationError):
            SearchRelevanceJudgment(product_id="P1", grade=4)

    def test_empty_benchmark_rejected(self) -> None:
        with pytest.raises(ValidationError, match="at least one query"):
            SearchEvaluationBenchmark(metadata=_metadata(), queries=())


class TestMetricConfiguration:
    def test_invalid_k_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SearchMetricConfiguration(k_values=(0, 5))

    def test_k_values_sorted_unique(self) -> None:
        config = SearchMetricConfiguration(k_values=(10, 5, 10))
        assert config.k_values == (5, 10)


class TestEvaluationRequest:
    def test_frozen_and_extra_forbidden(self) -> None:
        request = SearchEvaluationRequest(
            benchmark=_benchmark(),
            variant=_variant(),
        )
        with pytest.raises(ValidationError):
            request.evaluation_version = "x"  # type: ignore[misc]
        with pytest.raises(ValidationError):
            SearchEvaluationRequest(
                benchmark=_benchmark(),
                variant=_variant(),
                unexpected=True,  # type: ignore[call-arg]
            )

    def test_evaluation_request_version(self) -> None:
        request = SearchEvaluationRequest(benchmark=_benchmark(), variant=_variant())
        assert request.evaluation_version == SEARCH_EVALUATION_CONTRACT_VERSION


class TestComparison:
    def test_comparison_delta_only(self) -> None:
        baseline = _result(variant_name="A", mrr=0.5)
        comparison = _result(variant_name="B", mrr=0.75)
        delta = compare_search_evaluation_variants(baseline, comparison)
        assert isinstance(delta, SearchExperimentComparison)
        assert delta.mrr_delta == pytest.approx(0.25)
        assert "winner" not in search_experiment_comparison_to_dict(delta)

    def test_incompatible_benchmark_raises(self) -> None:
        baseline = _result(variant_name="A", mrr=0.5)
        other = _result(variant_name="B", mrr=0.6)
        other_lineage = other.lineage.model_copy(update={"benchmark_version": "9.9.9"})
        other = other.model_copy(update={"lineage": other_lineage})
        with pytest.raises(LexicalRetrievalError, match="benchmark identity"):
            compare_search_evaluation_variants(baseline, other)


class TestSerializationDeterminism:
    def test_benchmark_json_stable(self) -> None:
        payload = search_evaluation_benchmark_to_dict(_benchmark())
        again = json.dumps(payload, sort_keys=True)
        assert again == json.dumps(payload, sort_keys=True)

    def test_result_json_stable(self) -> None:
        result = _result(variant_name="A", mrr=0.5)
        serialized = json.dumps(search_variant_evaluation_result_to_dict(result), sort_keys=True)
        assert serialized.count("evaluation_version") >= 1


class TestLexicalAdapter:
    def test_lexical_query_mapping(self) -> None:
        row = lexical_query_to_search_evaluation_query(
            query_id="q1",
            query_text="nike",
            category="brand",
            relevant_product_ids=("P1", "P2"),
        )
        assert row.relevance_judgments[0].grade == 2


class TestVariantIdentity:
    def test_variant_requires_name_and_version(self) -> None:
        with pytest.raises(ValidationError):
            SearchEvaluationVariant(variant_name="", variant_version="1.0.0")
