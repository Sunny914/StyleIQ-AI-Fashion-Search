"""Build canonical search evaluation reports from Phase 12 artifacts (Phase 12.10)."""

from __future__ import annotations

from pathlib import Path

from productiq.retrieval.evaluation.search_evaluation.baseline_schema import (
    SEARCH_BASELINE_ARTIFACT_SCHEMA_VERSION,
)
from productiq.retrieval.evaluation.search_evaluation.benchmark_artifact_schema import (
    SEARCH_BENCHMARK_ARTIFACT_SCHEMA_VERSION,
)
from productiq.retrieval.evaluation.search_evaluation.experiment_validation import (
    validate_shared_evaluation_envelope,
)
from productiq.retrieval.evaluation.search_evaluation.reporting.report_loader import (
    SearchEvaluationReportSources,
    load_search_evaluation_report_sources,
)
from productiq.retrieval.evaluation.search_evaluation.reporting.report_schema import (
    SEARCH_EVALUATION_REPORT_NAME,
    SEARCH_EVALUATION_REPORT_VERSION,
    SearchEvaluationBenchmarkReference,
    SearchEvaluationFailureAggregateSummaryRow,
    SearchEvaluationFailureAnalysisSummary,
    SearchEvaluationMetricSummaryRow,
    SearchEvaluationPairwiseComparisonRow,
    SearchEvaluationReport,
    SearchEvaluationReportConfiguration,
    SearchEvaluationReportMetadata,
    SearchEvaluationRetrievalPatternSummaryRow,
    SearchEvaluationStatisticalAnalysisSummary,
    SearchEvaluationStatisticalComparisonSummaryRow,
    SearchEvaluationVariantSummary,
)
from productiq.retrieval.evaluation.search_evaluation.reporting.report_validation import (
    validate_report_sources,
    validate_search_evaluation_report,
)
from productiq.retrieval.evaluation.search_evaluation.reporting.reproducibility import (
    build_reproducibility_manifest,
)
from productiq.retrieval.evaluation.search_evaluation.result_schema import (
    SearchExperimentComparison,
    SearchVariantEvaluationResult,
)

METRIC_FAMILIES: tuple[tuple[str, str], ...] = (
    ("precision_at_k", "mean_precision_at_k"),
    ("recall_at_k", "mean_recall_at_k"),
    ("hit_rate_at_k", "mean_hit_rate_at_k"),
    ("ndcg_at_k", "mean_ndcg_at_k"),
)


def _int_key_map(values: dict[int, float] | dict[str, float]) -> dict[int, float]:
    return {int(key): float(value) for key, value in values.items()}


def _aggregate_lookup(
    results: tuple[SearchVariantEvaluationResult, ...],
) -> dict[str, SearchVariantEvaluationResult]:
    return {row.lineage.variant_name: row for row in results}


def _metric_rows_from_aggregate(
    result: SearchVariantEvaluationResult,
) -> tuple[SearchEvaluationMetricSummaryRow, ...]:
    aggregate = result.aggregate
    rows: list[SearchEvaluationMetricSummaryRow] = []
    for metric_name, aggregate_field in METRIC_FAMILIES:
        values = _int_key_map(getattr(aggregate, aggregate_field))
        eligible = aggregate.recall_aggregate_query_count if metric_name == "recall_at_k" else None
        ndcg_eligible = aggregate.ndcg_aggregate_query_count if metric_name == "ndcg_at_k" else None
        for k in sorted(values):
            count = eligible if metric_name == "recall_at_k" else ndcg_eligible
            rows.append(
                SearchEvaluationMetricSummaryRow(
                    metric_name=metric_name,
                    k=k,
                    value=values[k],
                    eligible_query_count=count,
                )
            )
    rows.append(
        SearchEvaluationMetricSummaryRow(
            metric_name="mrr",
            k=None,
            value=aggregate.mrr,
            eligible_query_count=aggregate.query_count,
        )
    )
    return tuple(rows)


def _variant_summary_from_baseline(bundle: object) -> SearchEvaluationVariantSummary:
    from productiq.retrieval.evaluation.search_evaluation.reporting.report_loader import (
        BaselineArtifactBundle,
    )

    if not isinstance(bundle, BaselineArtifactBundle):
        msg = "expected BaselineArtifactBundle"
        raise TypeError(msg)
    result = bundle.evaluation_result
    aggregate = result.aggregate
    provenance = bundle.payload.get("retrieval_provenance")
    mode: str | None = None
    if isinstance(provenance, dict):
        raw = provenance.get("index_mode") or provenance.get("bm25_index_mode")
        if isinstance(raw, str):
            mode = raw
    checksum = bundle.payload.get("deterministic_checksum_sha256")
    return SearchEvaluationVariantSummary(
        variant_name=result.lineage.variant_name,
        variant_version=result.lineage.variant_version,
        source_phase="12.5",
        artifact_path=bundle.artifact_path,
        artifact_schema_version=SEARCH_BASELINE_ARTIFACT_SCHEMA_VERSION,
        artifact_checksum_sha256=str(checksum) if isinstance(checksum, str) else None,
        retrieval_index_mode=mode,
        query_count=aggregate.query_count,
        recall_aggregate_query_count=aggregate.recall_aggregate_query_count,
        ndcg_aggregate_query_count=aggregate.ndcg_aggregate_query_count,
        metrics=_metric_rows_from_aggregate(result),
    )


def _pairwise_rows_from_comparison(
    comparison: SearchExperimentComparison,
    *,
    source: str,
    lookup: dict[str, SearchVariantEvaluationResult],
) -> tuple[SearchEvaluationPairwiseComparisonRow, ...]:
    reference = lookup.get(comparison.baseline_variant)
    if reference is None:
        return ()
    rows: list[SearchEvaluationPairwiseComparisonRow] = []
    ref_agg = reference.aggregate
    precision_d = _int_key_map(comparison.precision_at_k_delta)
    recall_d = _int_key_map(comparison.recall_at_k_delta)
    hit_d = _int_key_map(comparison.hit_rate_at_k_delta)
    ndcg_d = _int_key_map(comparison.ndcg_at_k_delta)
    ref_precision = _int_key_map(ref_agg.mean_precision_at_k)
    ref_recall = _int_key_map(ref_agg.mean_recall_at_k)
    ref_hit = _int_key_map(ref_agg.mean_hit_rate_at_k)
    ref_ndcg = _int_key_map(ref_agg.mean_ndcg_at_k)
    for k in sorted(ref_precision):
        ref_val = ref_precision[k]
        delta = precision_d[k]
        rows.append(
            SearchEvaluationPairwiseComparisonRow(
                comparison_source=source,  # type: ignore[arg-type]
                reference_variant_name=comparison.baseline_variant,
                candidate_variant_name=comparison.comparison_variant,
                metric_name="precision_at_k",
                k=k,
                reference_value=ref_val,
                candidate_value=ref_val + delta,
                absolute_delta=delta,
            )
        )
    for k in sorted(ref_recall):
        ref_val = ref_recall[k]
        delta = recall_d[k]
        rows.append(
            SearchEvaluationPairwiseComparisonRow(
                comparison_source=source,  # type: ignore[arg-type]
                reference_variant_name=comparison.baseline_variant,
                candidate_variant_name=comparison.comparison_variant,
                metric_name="recall_at_k",
                k=k,
                reference_value=ref_val,
                candidate_value=ref_val + delta,
                absolute_delta=delta,
            )
        )
    for k in sorted(ref_hit):
        ref_val = ref_hit[k]
        delta = hit_d[k]
        rows.append(
            SearchEvaluationPairwiseComparisonRow(
                comparison_source=source,  # type: ignore[arg-type]
                reference_variant_name=comparison.baseline_variant,
                candidate_variant_name=comparison.comparison_variant,
                metric_name="hit_rate_at_k",
                k=k,
                reference_value=ref_val,
                candidate_value=ref_val + delta,
                absolute_delta=delta,
            )
        )
    for k in sorted(ref_ndcg):
        ref_val = ref_ndcg[k]
        delta = ndcg_d[k]
        rows.append(
            SearchEvaluationPairwiseComparisonRow(
                comparison_source=source,  # type: ignore[arg-type]
                reference_variant_name=comparison.baseline_variant,
                candidate_variant_name=comparison.comparison_variant,
                metric_name="ndcg_at_k",
                k=k,
                reference_value=ref_val,
                candidate_value=ref_val + delta,
                absolute_delta=delta,
            )
        )
    ref_mrr = ref_agg.mrr
    mrr_delta = comparison.mrr_delta
    rows.append(
        SearchEvaluationPairwiseComparisonRow(
            comparison_source=source,  # type: ignore[arg-type]
            reference_variant_name=comparison.baseline_variant,
            candidate_variant_name=comparison.comparison_variant,
            metric_name="mrr",
            k=None,
            reference_value=ref_mrr,
            candidate_value=ref_mrr + mrr_delta,
            absolute_delta=mrr_delta,
        )
    )
    return tuple(rows)


def build_search_evaluation_report(
    sources: SearchEvaluationReportSources,
) -> SearchEvaluationReport:
    from productiq.retrieval.evaluation.search_evaluation.hardening.validation import (
        validate_search_evaluation_hardening_sources,
    )

    validate_report_sources(sources)
    validate_search_evaluation_hardening_sources(sources)
    baseline_results = tuple(row.evaluation_result for row in sources.baselines)
    envelope = validate_shared_evaluation_envelope(baseline_results)
    lookup = _aggregate_lookup(baseline_results)
    if sources.ranking_experiment is not None:
        for row in sources.ranking_experiment.variant_evaluation_results:
            lookup[row.lineage.variant_name] = row

    benchmark_checksum = sources.benchmark_payload.get("deterministic_checksum_sha256")
    metadata = SearchEvaluationReportMetadata(
        report_name=SEARCH_EVALUATION_REPORT_NAME,
        report_version=SEARCH_EVALUATION_REPORT_VERSION,
        description="Phase 12 evaluation reporting and reproducibility synthesis.",
    )
    benchmark_ref = SearchEvaluationBenchmarkReference(
        benchmark_name=sources.benchmark.metadata.benchmark_name,
        benchmark_version=sources.benchmark.metadata.benchmark_version,
        benchmark_artifact_path=sources.benchmark_path,
        benchmark_artifact_schema_version=str(
            sources.benchmark_payload.get(
                "artifact_schema_version", SEARCH_BENCHMARK_ARTIFACT_SCHEMA_VERSION
            )
        ),
        benchmark_checksum_sha256=str(benchmark_checksum)
        if isinstance(benchmark_checksum, str)
        else None,
        query_count=len(sources.benchmark.queries),
    )
    exec_top_k = sources.baselines[0].payload.get("execution_configuration")
    execution_top_k = envelope.metric_configuration.execution_top_k
    if isinstance(exec_top_k, dict) and isinstance(exec_top_k.get("execution_top_k"), int):
        execution_top_k = exec_top_k["execution_top_k"]

    configuration = SearchEvaluationReportConfiguration(
        metric_configuration=envelope.metric_configuration,
        execution_top_k=execution_top_k,
        evaluation_top_k=envelope.metric_configuration.evaluation_top_k,
    )

    variant_summaries: list[SearchEvaluationVariantSummary] = [
        _variant_summary_from_baseline(bundle) for bundle in sources.baselines
    ]
    if sources.ranking_experiment is not None:
        from productiq.retrieval.evaluation.search_evaluation.ranking_experiment_schema import (
            SEARCH_RANKING_EXPERIMENT_ARTIFACT_SCHEMA_VERSION,
        )

        for result in sorted(
            sources.ranking_experiment.variant_evaluation_results,
            key=lambda row: row.lineage.variant_name,
        ):
            variant_summaries.append(
                SearchEvaluationVariantSummary(
                    variant_name=result.lineage.variant_name,
                    variant_version=result.lineage.variant_version,
                    source_phase="12.7",
                    artifact_path="resources/evaluation/productiq_search_ranking_experiment_v1.json",
                    artifact_schema_version=SEARCH_RANKING_EXPERIMENT_ARTIFACT_SCHEMA_VERSION,
                    artifact_checksum_sha256=(
                        str(sources.ranking_experiment_payload.get("deterministic_checksum_sha256"))
                        if sources.ranking_experiment_payload
                        and isinstance(
                            sources.ranking_experiment_payload.get("deterministic_checksum_sha256"),
                            str,
                        )
                        else None
                    ),
                    retrieval_index_mode=None,
                    query_count=result.aggregate.query_count,
                    recall_aggregate_query_count=result.aggregate.recall_aggregate_query_count,
                    ndcg_aggregate_query_count=result.aggregate.ndcg_aggregate_query_count,
                    metrics=_metric_rows_from_aggregate(result),
                )
            )

    pairwise: list[SearchEvaluationPairwiseComparisonRow] = []
    if sources.baseline_experiment is not None:
        for comparison in sources.baseline_experiment.candidate_comparisons:
            pairwise.extend(
                _pairwise_rows_from_comparison(
                    comparison,
                    source="baseline_experiment",
                    lookup=lookup,
                )
            )
    if sources.ranking_experiment is not None:
        rank_lookup = {
            row.lineage.variant_name: row
            for row in sources.ranking_experiment.variant_evaluation_results
        }
        for comparison in sources.ranking_experiment.candidate_comparisons:
            pairwise.extend(
                _pairwise_rows_from_comparison(
                    comparison,
                    source="ranking_experiment",
                    lookup=rank_lookup,
                )
            )

    failure_summary: SearchEvaluationFailureAnalysisSummary | None = None
    if sources.failure_analysis is not None:
        failure_summary = SearchEvaluationFailureAnalysisSummary(
            analysis_artifact_path="resources/evaluation/productiq_search_failure_analysis_v1.json",
            analysis_artifact_schema_version="12.8.0",
            failure_record_count=len(sources.failure_analysis.records),
            aggregate_rows=tuple(
                SearchEvaluationFailureAggregateSummaryRow(
                    variant_name=row.variant_name,
                    analysis_k=row.analysis_k,
                    failure_category=row.failure_category.value,
                    record_count=row.record_count,
                )
                for row in sorted(
                    sources.failure_analysis.aggregates,
                    key=lambda item: (
                        item.variant_name,
                        item.analysis_k,
                        item.failure_category.value,
                    ),
                )
            ),
            retrieval_pattern_rows=tuple(
                SearchEvaluationRetrievalPatternSummaryRow(
                    pattern=row.pattern,
                    product_count=row.product_count,
                )
                for row in sorted(
                    sources.failure_analysis.retrieval_relationship_aggregates,
                    key=lambda item: item.pattern,
                )
            ),
            diagnostic_limitations=sources.failure_analysis.provenance_notes,
        )

    statistical_summary: SearchEvaluationStatisticalAnalysisSummary | None = None
    if sources.statistical_analysis is not None:
        stat_rows: list[SearchEvaluationStatisticalComparisonSummaryRow] = []
        for stat_row in sorted(
            sources.statistical_analysis.comparisons,
            key=lambda item: (
                item.reference_variant_name,
                item.candidate_variant_name,
                item.metric_name.value,
                item.k if item.k is not None else -1,
            ),
        ):
            ci = stat_row.confidence_interval
            stat_rows.append(
                SearchEvaluationStatisticalComparisonSummaryRow(
                    reference_variant_name=stat_row.reference_variant_name,
                    candidate_variant_name=stat_row.candidate_variant_name,
                    metric_name=stat_row.metric_name.value,
                    k=stat_row.k,
                    total_queries=stat_row.total_queries,
                    eligible_queries=stat_row.eligible_queries,
                    excluded_queries=stat_row.excluded_queries,
                    exclusion_reasons=stat_row.exclusion_reasons,
                    reference_mean=stat_row.reference_mean,
                    candidate_mean=stat_row.candidate_mean,
                    observed_delta=stat_row.observed_delta,
                    bootstrap_n_samples=stat_row.bootstrap_configuration.n_bootstrap_samples,
                    bootstrap_confidence_level=stat_row.bootstrap_configuration.confidence_level,
                    bootstrap_random_seed=stat_row.bootstrap_configuration.random_seed,
                    confidence_interval_lower=ci.lower if ci else None,
                    confidence_interval_upper=ci.upper if ci else None,
                    permutation_n_samples=stat_row.permutation_configuration.n_permutations,
                    permutation_random_seed=stat_row.permutation_configuration.random_seed,
                    p_value=stat_row.p_value,
                    multiple_testing_method=stat_row.multiple_testing_method,
                    adjusted_p_value=stat_row.adjusted_p_value,
                    small_sample_warning=stat_row.small_sample_warning,
                )
            )
        statistical_summary = SearchEvaluationStatisticalAnalysisSummary(
            analysis_artifact_path="resources/evaluation/productiq_search_statistical_analysis_v1.json",
            analysis_artifact_schema_version="12.9.0",
            comparisons=tuple(stat_rows),
        )

    reproducibility = build_reproducibility_manifest(sources)
    report = SearchEvaluationReport(
        metadata=metadata,
        benchmark=benchmark_ref,
        configuration=configuration,
        variant_summaries=tuple(sorted(variant_summaries, key=lambda row: row.variant_name)),
        pairwise_comparisons=tuple(
            sorted(
                pairwise,
                key=lambda row: (
                    row.comparison_source,
                    row.reference_variant_name,
                    row.candidate_variant_name,
                    row.metric_name,
                    row.k if row.k is not None else -1,
                ),
            )
        ),
        failure_analysis=failure_summary,
        statistical_analysis=statistical_summary,
        reproducibility=reproducibility,
        limitations=(
            "Report values are copied from persisted Phase 12 artifacts; metrics are not recomputed.",
            "No winner, best variant, recommended, promotion, or deployment decision is selected.",
            *reproducibility.reproducibility_limitations,
        ),
    )
    validate_search_evaluation_report(report)
    return report


def build_search_evaluation_report_from_repo(repo_root: Path) -> SearchEvaluationReport:
    sources = load_search_evaluation_report_sources(repo_root)
    return build_search_evaluation_report(sources)


__all__ = [
    "build_search_evaluation_report",
    "build_search_evaluation_report_from_repo",
]
