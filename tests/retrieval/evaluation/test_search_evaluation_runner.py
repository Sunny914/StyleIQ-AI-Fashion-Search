"""Tests for Phase 12.4 search evaluation runner."""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import pytest
from pydantic import ValidationError

from productiq.exceptions import RetrievalError
from productiq.retrieval.evaluation.schema import DEFAULT_RETRIEVAL_EVALUATION_TOP_K
from productiq.retrieval.evaluation.search_evaluation import (
    MappingSearchEvaluationExecutor,
    SearchEvaluationBenchmark,
    SearchEvaluationBenchmarkMetadata,
    SearchEvaluationQuery,
    SearchEvaluationRequest,
    SearchEvaluationRunner,
    SearchEvaluationVariant,
    SearchMetricConfiguration,
    SearchRankedResultsForQuery,
    SearchRelevanceJudgment,
    build_search_evaluation_request,
    run_search_evaluation,
    search_variant_evaluation_result_to_dict,
)
from productiq.retrieval.evaluation.search_evaluation.run_context import SearchEvaluationRunContext


def _metadata() -> SearchEvaluationBenchmarkMetadata:
    return SearchEvaluationBenchmarkMetadata(
        benchmark_name="runner_test",
        benchmark_version="1.0.0",
        methodology="test",
        labeling_methodology="test",
        limitations="test",
        catalog_artifact="resources/processed/product_representations.parquet",
        source_representation_checksum="abc",
    )


def _query(query_id: str, *, product_id: str = "P1") -> SearchEvaluationQuery:
    return SearchEvaluationQuery(
        query_id=query_id,
        query_text=f"text for {query_id}",
        query_category="test",
        relevance_judgments=(SearchRelevanceJudgment(product_id=product_id, grade=2),),
    )


def _benchmark(*queries: SearchEvaluationQuery) -> SearchEvaluationBenchmark:
    return SearchEvaluationBenchmark(metadata=_metadata(), queries=queries)


def _request(
    benchmark: SearchEvaluationBenchmark,
    *,
    variant_name: str = "fake_variant",
    metric_configuration: SearchMetricConfiguration | None = None,
) -> SearchEvaluationRequest:
    variant = SearchEvaluationVariant(
        variant_name=variant_name,
        variant_version="1.0.0",
        lineage_labels=("toy",),
    )
    return build_search_evaluation_request(
        benchmark,
        variant,
        metric_configuration=metric_configuration,
    )


@dataclass
class _FailOnQueryExecutor:
    fail_query_id: str

    def execute_query(
        self,
        query: SearchEvaluationQuery,
        context: SearchEvaluationRunContext,
    ) -> SearchRankedResultsForQuery:
        if query.query_id == self.fail_query_id:
            msg = "simulated variant failure"
            raise RuntimeError(msg)
        return SearchRankedResultsForQuery(query_id=query.query_id, ranked_product_ids=("P1",))


@dataclass
class _WrongQueryIdExecutor:
    def execute_query(
        self,
        query: SearchEvaluationQuery,
        context: SearchEvaluationRunContext,
    ) -> SearchRankedResultsForQuery:
        return SearchRankedResultsForQuery(query_id="wrong_id", ranked_product_ids=("P1",))


@dataclass
class _DuplicateRankExecutor:
    def execute_query(
        self,
        query: SearchEvaluationQuery,
        context: SearchEvaluationRunContext,
    ) -> SearchRankedResultsForQuery:
        return SearchRankedResultsForQuery(query_id=query.query_id, ranked_product_ids=("A", "A"))


@dataclass
class _RecordingExecutor:
    execution_top_k_values: list[int] = field(default_factory=list)

    def execute_query(
        self,
        query: SearchEvaluationQuery,
        context: SearchEvaluationRunContext,
    ) -> SearchRankedResultsForQuery:
        self.execution_top_k_values.append(context.execution_top_k)
        return SearchRankedResultsForQuery(query_id=query.query_id, ranked_product_ids=())


class TestRunnerHappyPath:
    def test_single_query_benchmark(self) -> None:
        benchmark = _benchmark(_query("q1"))
        rankings = {"q1": ("P1", "X")}
        request = _request(benchmark)
        result = run_search_evaluation(request, MappingSearchEvaluationExecutor(rankings))
        assert len(result.per_query) == 1
        assert result.per_query[0].query_id == "q1"
        assert result.aggregate.query_count == 1
        assert result.per_query[0].precision_at_k[1] == pytest.approx(1.0)

    def test_multiple_queries_deterministic_order(self) -> None:
        benchmark = _benchmark(_query("q_b"), _query("q_a", product_id="P2"))
        rankings = {"q_a": ("P2",), "q_b": ("P1",)}
        request = _request(benchmark)
        result = run_search_evaluation(request, MappingSearchEvaluationExecutor(rankings))
        assert [row.query_id for row in result.per_query] == ["q_a", "q_b"]

    def test_empty_ranking_is_valid(self) -> None:
        benchmark = _benchmark(_query("q1"))
        request = _request(benchmark)
        result = run_search_evaluation(
            request,
            MappingSearchEvaluationExecutor({"q1": ()}),
        )
        assert result.per_query[0].ranked_product_ids == ()
        assert result.per_query[0].precision_at_k[5] == pytest.approx(0.0)

    def test_two_variants_same_runner(self) -> None:
        benchmark = _benchmark(_query("q1"))
        rankings_a = {"q1": ("P1", "X")}
        rankings_b = {"q1": ("X", "P1")}
        request_a = _request(benchmark, variant_name="A")
        request_b = _request(benchmark, variant_name="B")
        result_a = run_search_evaluation(request_a, MappingSearchEvaluationExecutor(rankings_a))
        result_b = run_search_evaluation(request_b, MappingSearchEvaluationExecutor(rankings_b))
        assert result_a.lineage.variant_name == "A"
        assert result_b.lineage.variant_name == "B"
        assert result_a.per_query[0].reciprocal_rank == pytest.approx(1.0)
        assert result_b.per_query[0].reciprocal_rank == pytest.approx(0.5)


class TestRunnerFailures:
    def test_empty_benchmark_rejected_by_contract(self) -> None:
        with pytest.raises(ValidationError, match="at least one query"):
            _benchmark()

    def test_variant_exception_fail_fast(self) -> None:
        benchmark = _benchmark(_query("q1"), _query("q2", product_id="P2"))
        request = _request(benchmark)
        with pytest.raises(RetrievalError, match="q1"):
            run_search_evaluation(request, _FailOnQueryExecutor(fail_query_id="q1"))

    def test_wrong_query_id_from_executor(self) -> None:
        request = _request(_benchmark(_query("q1")))
        with pytest.raises(RetrievalError, match="query_id"):
            run_search_evaluation(request, _WrongQueryIdExecutor())

    def test_duplicate_ranked_product_ids(self) -> None:
        request = _request(_benchmark(_query("q1")))
        with pytest.raises(RetrievalError, match="invalid ranked results"):
            run_search_evaluation(request, _DuplicateRankExecutor())


class TestConfigurationAndLineage:
    def test_execution_top_k_propagated_to_executor(self) -> None:
        benchmark = _benchmark(_query("q1"))
        config = SearchMetricConfiguration(execution_top_k=7, evaluation_top_k=5)
        request = _request(benchmark, metric_configuration=config)
        recorder = _RecordingExecutor()
        run_search_evaluation(request, recorder)
        assert recorder.execution_top_k_values == [7]

    def test_default_execution_top_k(self) -> None:
        config = SearchMetricConfiguration()
        assert config.execution_top_k == DEFAULT_RETRIEVAL_EVALUATION_TOP_K

    def test_lineage_propagation(self) -> None:
        benchmark = _benchmark(_query("q1"))
        config = SearchMetricConfiguration(k_values=(1, 3), evaluation_top_k=3, min_relevant_grade=2)
        request = _request(benchmark, metric_configuration=config)
        result = run_search_evaluation(
            request,
            MappingSearchEvaluationExecutor({"q1": ("P1",)}),
        )
        lineage = result.lineage
        assert lineage.benchmark_name == "runner_test"
        assert lineage.benchmark_version == "1.0.0"
        assert lineage.variant_name == "fake_variant"
        assert lineage.metric_configuration.k_values == (1, 3)
        assert lineage.catalog_artifact == benchmark.metadata.catalog_artifact
        assert lineage.source_representation_checksum == "abc"
        assert lineage.variant_lineage_labels == ("toy",)
        assert result.evaluation_version == request.evaluation_version

    def test_deterministic_repeated_run(self) -> None:
        benchmark = _benchmark(_query("q1"), _query("q2", product_id="P2"))
        rankings = {"q1": ("P1",), "q2": ("P2",)}
        request = _request(benchmark)
        executor = MappingSearchEvaluationExecutor(rankings)
        first = run_search_evaluation(request, executor)
        second = run_search_evaluation(request, executor)
        assert json.dumps(search_variant_evaluation_result_to_dict(first), sort_keys=True) == json.dumps(
            search_variant_evaluation_result_to_dict(second),
            sort_keys=True,
        )

    def test_runner_class_entry_point(self) -> None:
        request = _request(_benchmark(_query("q1")))
        result = SearchEvaluationRunner().run(
            request,
            MappingSearchEvaluationExecutor({"q1": ("P1",)}),
        )
        assert result.aggregate.mrr == pytest.approx(1.0)
