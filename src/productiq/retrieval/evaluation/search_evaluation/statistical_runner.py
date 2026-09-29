"""Run paired statistical analysis over Phase 12 evaluation artifacts (Phase 12.9)."""

from __future__ import annotations

from pathlib import Path

from productiq.exceptions.base import RetrievalError
from productiq.retrieval.evaluation.search_evaluation.baseline_schema import (
    SEARCH_BASELINE_BM25_RUN_FILENAME,
    SEARCH_BASELINE_BM25_VARIANT_NAME,
    SEARCH_BASELINE_RRF_RUN_FILENAME,
    SEARCH_BASELINE_RRF_VARIANT_NAME,
    SEARCH_BASELINE_SEMANTIC_RUN_FILENAME,
    SEARCH_BASELINE_SEMANTIC_VARIANT_NAME,
)
from productiq.retrieval.evaluation.search_evaluation.bootstrap import bootstrap_mean_ci
from productiq.retrieval.evaluation.search_evaluation.experiment_loader import (
    load_variant_evaluation_from_baseline_artifact,
)
from productiq.retrieval.evaluation.search_evaluation.permutation_test import (
    paired_sign_flip_p_value,
)
from productiq.retrieval.evaluation.search_evaluation.ranking_experiment_artifact import (
    load_validated_ranking_experiment_artifact,
)
from productiq.retrieval.evaluation.search_evaluation.ranking_experiment_schema import (
    SEARCH_RANKING_EXPERIMENT_FILENAME,
    SearchRankingExperimentResult,
)
from productiq.retrieval.evaluation.search_evaluation.request_schema import (
    SearchMetricConfiguration,
)
from productiq.retrieval.evaluation.search_evaluation.result_schema import (
    SearchVariantEvaluationResult,
)
from productiq.retrieval.evaluation.search_evaluation.statistical_artifact import (
    build_search_statistical_analysis_artifact_dict,
    write_search_statistical_analysis_artifact,
)
from productiq.retrieval.evaluation.search_evaluation.statistical_observations import (
    build_paired_observations,
    mean_absolute_paired_difference,
    mean_values,
)
from productiq.retrieval.evaluation.search_evaluation.statistical_schema import (
    SEARCH_STATISTICAL_ANALYSIS_FILENAME,
    SEARCH_STATISTICAL_ANALYSIS_NAME,
    SEARCH_STATISTICAL_ANALYSIS_VERSION,
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
    validate_shared_metric_configuration,
)


def _small_sample_warning(sample_size: int, threshold: int) -> str | None:
    if sample_size >= threshold:
        return None
    return (
        f"Eligible paired query count is {sample_size} (threshold {threshold}); "
        "statistical summaries are conditional on the curated benchmark sample and "
        "must not be interpreted as population-level or production-traffic evidence."
    )


def metric_k_comparisons_for_configuration(
    metric_configuration: SearchMetricConfiguration,
) -> tuple[tuple[SearchStatisticalMetricName, int | None], ...]:
    rows: list[tuple[SearchStatisticalMetricName, int | None]] = []
    for k in metric_configuration.k_values:
        rows.append((SearchStatisticalMetricName.PRECISION_AT_K, k))
        rows.append((SearchStatisticalMetricName.RECALL_AT_K, k))
        rows.append((SearchStatisticalMetricName.HIT_RATE_AT_K, k))
        if metric_configuration.compute_ndcg:
            rows.append((SearchStatisticalMetricName.NDCG_AT_K, k))
    rows.append((SearchStatisticalMetricName.MRR, None))
    return tuple(rows)


def compare_variants_statistically(
    reference: SearchVariantEvaluationResult,
    candidate: SearchVariantEvaluationResult,
    *,
    comparison_source: str,
    configuration: SearchStatisticalAnalysisConfiguration,
) -> tuple[SearchMetricStatisticalComparison, ...]:
    validate_shared_metric_configuration(
        reference.lineage.metric_configuration,
        candidate.lineage.metric_configuration,
    )
    metric_configuration = reference.lineage.metric_configuration
    comparisons: list[SearchMetricStatisticalComparison] = []
    for metric_name, k in metric_k_comparisons_for_configuration(metric_configuration):
        validate_k_for_metric(metric_name, k, metric_configuration)
        observations = build_paired_observations(
            reference,
            candidate,
            metric_name=metric_name,
            k=k,
        )
        ref_mean = mean_values(observations.reference_values)
        cand_mean = mean_values(observations.candidate_values)
        delta = mean_values(observations.paired_differences)
        mad = mean_absolute_paired_difference(observations.paired_differences)
        ci = None
        p_value = None
        if observations.eligible_queries > 0:
            ci = bootstrap_mean_ci(observations.paired_differences, configuration.bootstrap)
            p_value = paired_sign_flip_p_value(
                observations.paired_differences,
                n_permutations=configuration.permutation.n_permutations,
                random_seed=configuration.permutation.random_seed,
            )
        comparisons.append(
            SearchMetricStatisticalComparison(
                reference_variant_name=reference.lineage.variant_name,
                candidate_variant_name=candidate.lineage.variant_name,
                comparison_source=comparison_source,  # type: ignore[arg-type]
                metric_name=metric_name,
                k=k,
                total_queries=observations.total_queries,
                eligible_queries=observations.eligible_queries,
                excluded_queries=observations.excluded_queries,
                exclusion_reasons=observations.exclusion_reasons,
                sample_size=observations.eligible_queries,
                reference_mean=ref_mean,
                candidate_mean=cand_mean,
                observed_delta=delta,
                mean_absolute_paired_difference=mad,
                bootstrap_configuration=configuration.bootstrap,
                confidence_interval=ci,
                permutation_configuration=configuration.permutation,
                p_value=p_value,
                multiple_testing_method=configuration.multiple_testing_method,
                small_sample_warning=_small_sample_warning(
                    observations.eligible_queries,
                    configuration.small_sample_query_threshold,
                ),
            )
        )
    return tuple(comparisons)


def apply_multiple_testing_adjustment(
    comparisons: tuple[SearchMetricStatisticalComparison, ...],
    method: str,
) -> tuple[SearchMetricStatisticalComparison, ...]:
    if method != "benjamini_hochberg":
        return comparisons
    raw = tuple(row.p_value for row in comparisons)
    adjusted = benjamini_hochberg_adjusted_p_values(raw)
    updated: list[SearchMetricStatisticalComparison] = []
    for row, adj in zip(comparisons, adjusted, strict=True):
        updated.append(row.model_copy(update={"adjusted_p_value": adj}))
    return tuple(updated)


def build_default_statistical_configuration() -> SearchStatisticalAnalysisConfiguration:
    return SearchStatisticalAnalysisConfiguration(
        comparison_pairs=(
            SearchVariantComparisonPair(
                reference_variant_name=SEARCH_BASELINE_BM25_VARIANT_NAME,
                candidate_variant_name=SEARCH_BASELINE_SEMANTIC_VARIANT_NAME,
                source="baseline_artifact",
            ),
            SearchVariantComparisonPair(
                reference_variant_name=SEARCH_BASELINE_BM25_VARIANT_NAME,
                candidate_variant_name=SEARCH_BASELINE_RRF_VARIANT_NAME,
                source="baseline_artifact",
            ),
        ),
    )


def _load_baseline_variants(repo_root: Path) -> tuple[dict[str, SearchVariantEvaluationResult], list[str]]:
    eval_dir = repo_root / "resources" / "evaluation"
    mapping = {
        SEARCH_BASELINE_BM25_VARIANT_NAME: SEARCH_BASELINE_BM25_RUN_FILENAME,
        SEARCH_BASELINE_SEMANTIC_VARIANT_NAME: SEARCH_BASELINE_SEMANTIC_RUN_FILENAME,
        SEARCH_BASELINE_RRF_VARIANT_NAME: SEARCH_BASELINE_RRF_RUN_FILENAME,
    }
    results: dict[str, SearchVariantEvaluationResult] = {}
    refs: list[str] = []
    for variant_name, filename in sorted(mapping.items()):
        path = eval_dir / filename
        if not path.is_file():
            msg = f"missing baseline artifact for statistical analysis: {path}"
            raise RetrievalError(msg)
        result, _payload = load_variant_evaluation_from_baseline_artifact(path)
        if result.lineage.variant_name != variant_name:
            msg = f"unexpected variant_name in {filename}"
            raise RetrievalError(msg)
        results[variant_name] = result
        refs.append(f"resources/evaluation/{filename}")
    return results, refs


def _load_ranking_variants(
    repo_root: Path,
) -> tuple[dict[str, SearchVariantEvaluationResult], str | None, SearchRankingExperimentResult | None]:
    path = repo_root / "resources" / "evaluation" / SEARCH_RANKING_EXPERIMENT_FILENAME
    if not path.is_file():
        return {}, None, None
    payload = load_validated_ranking_experiment_artifact(path)
    raw = payload.get("experiment_result")
    if not isinstance(raw, dict):
        msg = "ranking experiment artifact missing experiment_result"
        raise RetrievalError(msg)
    experiment = SearchRankingExperimentResult.model_validate(raw)
    results = {
        row.lineage.variant_name: row for row in experiment.variant_evaluation_results
    }
    ref = f"resources/evaluation/{SEARCH_RANKING_EXPERIMENT_FILENAME}"
    return results, ref, experiment


def _resolve_variant_result(
    name: str,
    source: str,
    baseline: dict[str, SearchVariantEvaluationResult],
    ranking: dict[str, SearchVariantEvaluationResult],
) -> SearchVariantEvaluationResult:
    pool = baseline if source == "baseline_artifact" else ranking
    if name not in pool:
        msg = f"variant {name!r} not available from source {source!r}"
        raise RetrievalError(msg)
    return pool[name]


def run_search_statistical_analysis(
    repo_root: Path,
    *,
    configuration: SearchStatisticalAnalysisConfiguration | None = None,
) -> SearchStatisticalAnalysisResult:
    root = Path(repo_root)
    config = configuration or build_default_statistical_configuration()
    baseline_variants, baseline_refs = _load_baseline_variants(root)
    ranking_variants, ranking_ref, ranking_experiment = _load_ranking_variants(root)

    pairs = list(config.comparison_pairs)
    if ranking_experiment is not None:
        ref_name = ranking_experiment.reference_ranking_variant_name
        for row in ranking_experiment.variant_evaluation_results:
            if row.lineage.variant_name == ref_name:
                continue
            pairs.append(
                SearchVariantComparisonPair(
                    reference_variant_name=ref_name,
                    candidate_variant_name=row.lineage.variant_name,
                    source="ranking_experiment",
                )
            )
        effective_config = config.model_copy(update={"comparison_pairs": tuple(pairs)})
    else:
        effective_config = config

    all_comparisons: list[SearchMetricStatisticalComparison] = []
    for pair in effective_config.comparison_pairs:
        reference = _resolve_variant_result(
            pair.reference_variant_name,
            pair.source,
            baseline_variants,
            ranking_variants,
        )
        candidate = _resolve_variant_result(
            pair.candidate_variant_name,
            pair.source,
            baseline_variants,
            ranking_variants,
        )
        all_comparisons.extend(
            compare_variants_statistically(
                reference,
                candidate,
                comparison_source=pair.source,
                configuration=effective_config,
            )
        )

    sorted_comparisons = tuple(
        sorted(
            all_comparisons,
            key=lambda row: (
                row.reference_variant_name,
                row.candidate_variant_name,
                row.metric_name.value,
                row.k if row.k is not None else -1,
            ),
        )
    )
    adjusted = apply_multiple_testing_adjustment(
        sorted_comparisons,
        effective_config.multiple_testing_method,
    )
    benchmark = next(iter(baseline_variants.values()))
    lineage = SearchStatisticalAnalysisLineage(
        benchmark_name=benchmark.lineage.benchmark_name,
        benchmark_version=benchmark.lineage.benchmark_version,
        source_baseline_artifacts=tuple(sorted(baseline_refs)),
        source_ranking_experiment_artifact=ranking_ref,
    )
    return SearchStatisticalAnalysisResult(
        analysis_name=SEARCH_STATISTICAL_ANALYSIS_NAME,
        analysis_version=SEARCH_STATISTICAL_ANALYSIS_VERSION,
        description=(
            "Paired query-level statistical analysis over Phase 12.5 baselines "
            "and optional Phase 12.7 ranking experiment artifacts."
        ),
        configuration=effective_config,
        lineage=lineage,
        comparisons=adjusted,
    )


def run_default_search_statistical_analysis(repo_root: Path) -> SearchStatisticalAnalysisResult:
    result = run_search_statistical_analysis(repo_root)
    out_path = Path(repo_root) / "resources" / "evaluation" / SEARCH_STATISTICAL_ANALYSIS_FILENAME
    write_search_statistical_analysis_artifact(
        out_path,
        build_search_statistical_analysis_artifact_dict(result),
    )
    return result


__all__ = [
    "apply_multiple_testing_adjustment",
    "build_default_statistical_configuration",
    "compare_variants_statistically",
    "metric_k_comparisons_for_configuration",
    "run_default_search_statistical_analysis",
    "run_search_statistical_analysis",
]
