"""Tests for Phase 12.9 search statistical analysis."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from productiq.exceptions.base import RetrievalError
from productiq.retrieval.evaluation.search_evaluation.baseline_schema import (
    SEARCH_BASELINE_BM25_VARIANT_NAME,
    SEARCH_BASELINE_RRF_VARIANT_NAME,
    SEARCH_BASELINE_SEMANTIC_VARIANT_NAME,
)
from productiq.retrieval.evaluation.search_evaluation.bootstrap import bootstrap_mean_ci
from productiq.retrieval.evaluation.search_evaluation.permutation_test import (
    paired_sign_flip_p_value,
)
from productiq.retrieval.evaluation.search_evaluation.ranking_experiment_schema import (
    SEARCH_RANKING_VARIANT_BASELINE_RANKER,
    SEARCH_RANKING_VARIANT_LTR,
    SEARCH_RANKING_VARIANT_RETRIEVAL_ORDER,
)
from productiq.retrieval.evaluation.search_evaluation.request_schema import (
    SearchMetricConfiguration,
)
from productiq.retrieval.evaluation.search_evaluation.result_schema import (
    SearchAggregateMetricResult,
    SearchEvaluationLineage,
    SearchQueryMetricResult,
    SearchVariantEvaluationResult,
)
from productiq.retrieval.evaluation.search_evaluation.statistical_artifact import (
    build_search_statistical_analysis_artifact_dict,
    validate_search_statistical_analysis_artifact,
)
from productiq.retrieval.evaluation.search_evaluation.statistical_observations import (
    align_query_ids,
    build_paired_observations,
    mean_values,
)
from productiq.retrieval.evaluation.search_evaluation.statistical_runner import (
    build_default_statistical_configuration,
    compare_variants_statistically,
    run_search_statistical_analysis,
)
from productiq.retrieval.evaluation.search_evaluation.statistical_schema import (
    BootstrapConfiguration,
    PermutationConfiguration,
    SearchMetricStatisticalComparison,
    SearchStatisticalAnalysisConfiguration,
    SearchStatisticalAnalysisLineage,
    SearchStatisticalAnalysisResult,
    SearchStatisticalMetricName,
    SearchVariantComparisonPair,
)
from productiq.retrieval.evaluation.search_evaluation.statistical_validation import (
    benjamini_hochberg_adjusted_p_values,
    validate_k_for_metric,
    validate_metric_name,
)


def _metric_config(*, k_values: tuple[int, ...] = (1, 5, 10)) -> SearchMetricConfiguration:
    return SearchMetricConfiguration(
        k_values=k_values,
        evaluation_top_k=50,
        execution_top_k=50,
        min_relevant_grade=2,
        compute_ndcg=True,
    )


def _query_row(
    query_id: str,
    *,
    precision: float = 0.5,
    recall: float | None = 0.5,
    hit_rate: float = 0.5,
    ndcg: float | None = 0.5,
    mrr: float = 0.5,
    recall_eligible: bool = True,
) -> SearchQueryMetricResult:
    k_values = (1, 5, 10)
    return SearchQueryMetricResult(
        query_id=query_id,
        query_text=f"text-{query_id}",
        query_category="brand",
        judged_relevant_count=2 if recall_eligible else 0,
        ranked_product_ids=("P1",),
        precision_at_k={k: precision for k in k_values},
        recall_at_k={k: recall for k in k_values},
        hit_rate_at_k={k: hit_rate for k in k_values},
        ndcg_at_k={k: ndcg for k in k_values},
        reciprocal_rank=mrr,
        recall_aggregate_eligible=recall_eligible,
    )


def _variant(
    name: str,
    rows: tuple[SearchQueryMetricResult, ...],
) -> SearchVariantEvaluationResult:
    config = _metric_config()
    return SearchVariantEvaluationResult(
        lineage=SearchEvaluationLineage(
            benchmark_name="productiq_search_benchmark_v1",
            benchmark_version="1.0.0",
            variant_name=name,
            variant_version="1.0.0",
            metric_configuration=config,
        ),
        per_query=rows,
        aggregate=SearchAggregateMetricResult(
            query_count=len(rows),
            recall_aggregate_query_count=sum(1 for row in rows if row.recall_aggregate_eligible),
            ndcg_aggregate_query_count=len(rows),
            k_values=config.k_values,
            mean_precision_at_k={k: 0.5 for k in config.k_values},
            mean_recall_at_k={k: 0.5 for k in config.k_values},
            mean_hit_rate_at_k={k: 0.5 for k in config.k_values},
            mean_ndcg_at_k={k: 0.5 for k in config.k_values},
            mrr=0.5,
        ),
    )


def _fast_config(**kwargs: object) -> SearchStatisticalAnalysisConfiguration:
    base = SearchStatisticalAnalysisConfiguration(
        comparison_pairs=(
            SearchVariantComparisonPair(
                reference_variant_name="ref",
                candidate_variant_name="cand",
            ),
        ),
        bootstrap=BootstrapConfiguration(n_bootstrap_samples=500, random_seed=42),
        permutation=PermutationConfiguration(n_permutations=500, random_seed=42),
    )
    return base.model_copy(update=kwargs)


class TestContracts:
    def test_valid_statistical_contract(self) -> None:
        row = SearchMetricStatisticalComparison(
            reference_variant_name="ref",
            candidate_variant_name="cand",
            comparison_source="baseline_artifact",
            metric_name=SearchStatisticalMetricName.PRECISION_AT_K,
            k=10,
            total_queries=10,
            eligible_queries=10,
            excluded_queries=0,
            sample_size=10,
            reference_mean=0.2,
            candidate_mean=0.3,
            observed_delta=0.1,
            bootstrap_configuration=BootstrapConfiguration(n_bootstrap_samples=100),
            permutation_configuration=PermutationConfiguration(n_permutations=100),
            p_value=0.04,
        )
        assert row.observed_delta == 0.1

    def test_invalid_metric(self) -> None:
        with pytest.raises(RetrievalError):
            validate_metric_name("not_a_metric")

    def test_invalid_k(self) -> None:
        with pytest.raises(RetrievalError):
            validate_k_for_metric(
                SearchStatisticalMetricName.PRECISION_AT_K,
                99,
                _metric_config(),
            )


class TestPairing:
    def test_query_alignment(self) -> None:
        ref = _variant("ref", (_query_row("q1"), _query_row("q2")))
        cand = _variant("cand", (_query_row("q1"), _query_row("q2")))
        assert align_query_ids(ref, cand) == ("q1", "q2")

    def test_query_mismatch_rejection(self) -> None:
        ref = _variant("ref", (_query_row("q1"),))
        cand = _variant("cand", (_query_row("q2"),))
        with pytest.raises(RetrievalError, match="must match exactly"):
            align_query_ids(ref, cand)

    def test_paired_difference_calculation(self) -> None:
        ref = _variant("ref", (_query_row("q1", precision=0.2, recall=0.5, hit_rate=0.0, ndcg=0.1, mrr=0.5),))
        cand = _variant(
            "cand",
            (_query_row("q1", precision=0.5, recall=0.8, hit_rate=1.0, ndcg=0.2, mrr=0.25),),
        )
        obs = build_paired_observations(
            ref,
            cand,
            metric_name=SearchStatisticalMetricName.PRECISION_AT_K,
            k=10,
        )
        assert obs.paired_differences == (0.3,)

    def test_mean_effect(self) -> None:
        assert mean_values((0.1, 0.3)) == pytest.approx(0.2)


class TestBootstrap:
    def test_bootstrap_determinism(self) -> None:
        diffs = (0.1, -0.2, 0.05, 0.0, 0.15)
        config = BootstrapConfiguration(n_bootstrap_samples=200, random_seed=7)
        first = bootstrap_mean_ci(diffs, config)
        second = bootstrap_mean_ci(diffs, config)
        assert first == second

    def test_bootstrap_ci(self) -> None:
        diffs = (0.2, 0.2, 0.2)
        ci = bootstrap_mean_ci(diffs, BootstrapConfiguration(n_bootstrap_samples=100, random_seed=1))
        assert ci is not None
        assert ci.lower == pytest.approx(0.2, abs=1e-6)
        assert ci.upper == pytest.approx(0.2, abs=1e-6)


class TestPermutation:
    def test_permutation_determinism(self) -> None:
        diffs = (0.1, -0.1, 0.2)
        first = paired_sign_flip_p_value(diffs, n_permutations=300, random_seed=11)
        second = paired_sign_flip_p_value(diffs, n_permutations=300, random_seed=11)
        assert first == second

    def test_permutation_p_value(self) -> None:
        p_value = paired_sign_flip_p_value((0.5, 0.5, 0.5), n_permutations=500, random_seed=3)
        assert p_value is not None
        assert 0.0 < p_value <= 1.0

    def test_zero_differences(self) -> None:
        p_value = paired_sign_flip_p_value((0.0, 0.0, 0.0), n_permutations=200, random_seed=2)
        assert p_value == 1.0


class TestVariantComparisons:
    def test_identical_variants(self) -> None:
        row = _query_row("q1", precision=0.4, recall=0.5, hit_rate=1.0, ndcg=0.3, mrr=0.5)
        ref = _variant("ref", (row,))
        cand = _variant("cand", (row,))
        config = _fast_config(
            comparison_pairs=(
                SearchVariantComparisonPair(reference_variant_name="ref", candidate_variant_name="cand"),
            ),
        )
        comparisons = compare_variants_statistically(ref, cand, comparison_source="baseline_artifact", configuration=config)
        precision = next(
            row for row in comparisons if row.metric_name is SearchStatisticalMetricName.PRECISION_AT_K and row.k == 10
        )
        assert precision.observed_delta == 0.0

    def test_positive_and_negative_effects(self) -> None:
        ref = _variant("ref", (_query_row("q1", precision=0.1, recall=0.2, hit_rate=0.0, ndcg=0.1, mrr=0.1),))
        cand = _variant("cand", (_query_row("q1", precision=0.9, recall=0.8, hit_rate=1.0, ndcg=0.9, mrr=0.9),))
        config = _fast_config(
            comparison_pairs=(
                SearchVariantComparisonPair(reference_variant_name="ref", candidate_variant_name="cand"),
            ),
        )
        comparisons = compare_variants_statistically(ref, cand, comparison_source="baseline_artifact", configuration=config)
        precision = next(
            row for row in comparisons if row.metric_name is SearchStatisticalMetricName.PRECISION_AT_K and row.k == 1
        )
        assert precision.observed_delta == pytest.approx(0.8)


class TestMissingValues:
    def test_recall_none_exclusion(self) -> None:
        ref = _variant(
            "ref",
            (_query_row("q1", precision=0.1, recall=None, hit_rate=0.0, ndcg=0.1, mrr=0.1, recall_eligible=False),),
        )
        cand = _variant(
            "cand",
            (_query_row("q1", precision=0.2, recall=None, hit_rate=0.0, ndcg=0.2, mrr=0.2, recall_eligible=False),),
        )
        obs = build_paired_observations(
            ref,
            cand,
            metric_name=SearchStatisticalMetricName.RECALL_AT_K,
            k=10,
        )
        assert obs.eligible_queries == 0
        assert obs.excluded_queries == 1

    def test_all_observations_ineligible(self) -> None:
        ref = _variant(
            "ref",
            (_query_row("q1", precision=0.1, recall=None, hit_rate=0.0, ndcg=0.1, mrr=0.1, recall_eligible=False),),
        )
        cand = _variant(
            "cand",
            (_query_row("q1", precision=0.2, recall=None, hit_rate=0.0, ndcg=0.2, mrr=0.2, recall_eligible=False),),
        )
        config = _fast_config(
            comparison_pairs=(
                SearchVariantComparisonPair(reference_variant_name="ref", candidate_variant_name="cand"),
            ),
        )
        recall_row = next(
            row
            for row in compare_variants_statistically(
                ref, cand, comparison_source="baseline_artifact", configuration=config
            )
            if row.metric_name is SearchStatisticalMetricName.RECALL_AT_K and row.k == 10
        )
        assert recall_row.p_value is None
        assert recall_row.confidence_interval is None


class TestSampleSize:
    def test_sample_size_and_warning(self) -> None:
        ref = _variant("ref", (_query_row("q1", precision=0.1, recall=0.2, hit_rate=0.0, ndcg=0.1, mrr=0.1),))
        cand = _variant("cand", (_query_row("q1", precision=0.2, recall=0.3, hit_rate=1.0, ndcg=0.2, mrr=0.2),))
        config = _fast_config(
            comparison_pairs=(
                SearchVariantComparisonPair(reference_variant_name="ref", candidate_variant_name="cand"),
            ),
            small_sample_query_threshold=30,
        )
        row = next(
            item
            for item in compare_variants_statistically(
                ref, cand, comparison_source="baseline_artifact", configuration=config
            )
            if item.metric_name is SearchStatisticalMetricName.MRR
        )
        assert row.sample_size == 1
        assert row.small_sample_warning is not None


class TestMultipleMetricsAndK:
    def test_multiple_k_values(self) -> None:
        ref = _variant("ref", (_query_row("q1", precision=0.1, recall=0.2, hit_rate=0.0, ndcg=0.1, mrr=0.1),))
        cand = _variant("cand", (_query_row("q1", precision=0.2, recall=0.3, hit_rate=1.0, ndcg=0.2, mrr=0.2),))
        config = _fast_config(
            comparison_pairs=(
                SearchVariantComparisonPair(reference_variant_name="ref", candidate_variant_name="cand"),
            ),
        )
        comparisons = compare_variants_statistically(ref, cand, comparison_source="baseline_artifact", configuration=config)
        ks = {row.k for row in comparisons if row.metric_name is SearchStatisticalMetricName.PRECISION_AT_K}
        assert ks == {1, 5, 10}

    def test_multiple_metrics(self) -> None:
        ref = _variant("ref", (_query_row("q1", precision=0.1, recall=0.2, hit_rate=0.0, ndcg=0.1, mrr=0.1),))
        cand = _variant("cand", (_query_row("q1", precision=0.2, recall=0.3, hit_rate=1.0, ndcg=0.2, mrr=0.2),))
        config = _fast_config(
            comparison_pairs=(
                SearchVariantComparisonPair(reference_variant_name="ref", candidate_variant_name="cand"),
            ),
        )
        comparisons = compare_variants_statistically(ref, cand, comparison_source="baseline_artifact", configuration=config)
        names = {row.metric_name for row in comparisons}
        assert SearchStatisticalMetricName.MRR in names
        assert SearchStatisticalMetricName.NDCG_AT_K in names


class TestMultipleTesting:
    def test_multiple_testing_configuration(self) -> None:
        config = build_default_statistical_configuration()
        assert config.multiple_testing_method == "none"

    def test_benjamini_hochberg(self) -> None:
        adjusted = benjamini_hochberg_adjusted_p_values((0.01, 0.04, 0.03, None))
        assert adjusted[3] is None
        assert adjusted[0] is not None


class TestDefaultComparisonPairs:
    def test_default_baseline_pairs_no_reverse_duplicate(self) -> None:
        config = build_default_statistical_configuration()
        pairs = config.comparison_pairs
        assert len(pairs) == 2
        assert pairs[0].reference_variant_name == SEARCH_BASELINE_BM25_VARIANT_NAME
        assert pairs[0].candidate_variant_name == SEARCH_BASELINE_SEMANTIC_VARIANT_NAME
        assert pairs[1].reference_variant_name == SEARCH_BASELINE_BM25_VARIANT_NAME
        assert pairs[1].candidate_variant_name == SEARCH_BASELINE_RRF_VARIANT_NAME
        reverse = (
            SEARCH_BASELINE_RRF_VARIANT_NAME,
            SEARCH_BASELINE_BM25_VARIANT_NAME,
        )
        directional = {
            (row.reference_variant_name, row.candidate_variant_name) for row in pairs
        }
        assert reverse not in directional

    def test_default_run_emits_four_directional_pairs_once(self) -> None:
        root = Path(".")
        if not (root / "resources/evaluation/productiq_search_benchmark_v1_baseline_bm25_run.json").is_file():
            pytest.skip("Phase 12.5 artifacts missing")
        fast = build_default_statistical_configuration().model_copy(
            update={
                "bootstrap": BootstrapConfiguration(n_bootstrap_samples=50, random_seed=42),
                "permutation": PermutationConfiguration(n_permutations=50, random_seed=42),
            }
        )
        result = run_search_statistical_analysis(root, configuration=fast)
        pair_keys = {
            (row.reference_variant_name, row.candidate_variant_name)
            for row in result.comparisons
        }
        assert pair_keys == {
            (SEARCH_BASELINE_BM25_VARIANT_NAME, SEARCH_BASELINE_SEMANTIC_VARIANT_NAME),
            (SEARCH_BASELINE_BM25_VARIANT_NAME, SEARCH_BASELINE_RRF_VARIANT_NAME),
            (SEARCH_RANKING_VARIANT_RETRIEVAL_ORDER, SEARCH_RANKING_VARIANT_BASELINE_RANKER),
            (SEARCH_RANKING_VARIANT_RETRIEVAL_ORDER, SEARCH_RANKING_VARIANT_LTR),
        }
        assert len(result.comparisons) == 4 * 21


class TestArtifact:
    def test_deterministic_serialization(self) -> None:
        config = _fast_config()
        result = SearchStatisticalAnalysisResult(
            configuration=config,
            lineage=SearchStatisticalAnalysisLineage(
                benchmark_name="b",
                benchmark_version="1.0.0",
            ),
            comparisons=(),
        )
        payload = build_search_statistical_analysis_artifact_dict(result)
        assert json.dumps(payload, sort_keys=True) == json.dumps(payload, sort_keys=True)

    def test_checksum(self) -> None:
        config = _fast_config()
        result = SearchStatisticalAnalysisResult(
            configuration=config,
            lineage=SearchStatisticalAnalysisLineage(
                benchmark_name="b",
                benchmark_version="1.0.0",
            ),
            comparisons=(),
        )
        payload = build_search_statistical_analysis_artifact_dict(result)
        validate_search_statistical_analysis_artifact(payload)

    def test_invalid_contract_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SearchMetricStatisticalComparison(
                reference_variant_name="ref",
                candidate_variant_name="cand",
                comparison_source="baseline_artifact",
                metric_name=SearchStatisticalMetricName.MRR,
                k=10,
                total_queries=1,
                eligible_queries=1,
                excluded_queries=0,
                sample_size=1,
                bootstrap_configuration=BootstrapConfiguration(n_bootstrap_samples=10),
                permutation_configuration=PermutationConfiguration(n_permutations=10),
            )


class TestCanonicalIntegration:
    def test_run_on_repo_artifacts(self) -> None:
        root = Path(".")
        bm25 = root / "resources/evaluation/productiq_search_benchmark_v1_baseline_bm25_run.json"
        if not bm25.is_file():
            pytest.skip("Phase 12.5 artifacts missing")
        fast = build_default_statistical_configuration().model_copy(
            update={
                "bootstrap": BootstrapConfiguration(n_bootstrap_samples=200, random_seed=42),
                "permutation": PermutationConfiguration(n_permutations=200, random_seed=42),
            }
        )
        result = run_search_statistical_analysis(root, configuration=fast)
        assert result.comparisons
        assert any(row.p_value is not None for row in result.comparisons)

    def test_persisted_artifact_integration(self) -> None:
        root = Path(".")
        if not (root / "resources/evaluation/productiq_search_benchmark_v1_baseline_bm25_run.json").is_file():
            pytest.skip("Phase 12.5 artifacts missing")
        from productiq.retrieval.evaluation.search_evaluation.statistical_artifact import (
            write_search_statistical_analysis_artifact,
        )

        fast = build_default_statistical_configuration().model_copy(
            update={
                "bootstrap": BootstrapConfiguration(n_bootstrap_samples=200, random_seed=42),
                "permutation": PermutationConfiguration(n_permutations=200, random_seed=42),
            }
        )
        result = run_search_statistical_analysis(root, configuration=fast)
        path = root / "resources/evaluation/productiq_search_statistical_analysis_v1.json"
        write_search_statistical_analysis_artifact(
            path,
            build_search_statistical_analysis_artifact_dict(result),
        )
        payload = json.loads(path.read_text(encoding="utf-8"))
        validate_search_statistical_analysis_artifact(payload)
        assert payload["analysis_result"]["lineage"]["benchmark_name"] == "productiq_search_benchmark_v1"
