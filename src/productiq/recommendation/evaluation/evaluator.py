"""Recommendation offline evaluator (Phase 11.7)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field

from productiq.exceptions.base import RecommendationError
from productiq.ranking.evaluation.coverage import candidate_coverage_ratio
from productiq.recommendation.baseline_ranker_config import BASELINE_RECOMMENDATION_RANKER_VERSION
from productiq.recommendation.contracts import RankedRecommendation
from productiq.recommendation.evaluation.benchmark_schema import (
    RECOMMENDATION_VARIANT_BASELINE_11_5,
    RECOMMENDATION_VARIANT_BASELINE_11_5_PLUS_SELECTION_11_6,
    RecommendationBenchmark,
    RecommendationBenchmarkCase,
)
from productiq.recommendation.evaluation.comparison import compare_recommendation_variants
from productiq.recommendation.evaluation.constraint_metrics import (
    duplicate_recommendation_count,
    max_per_brand_violation_count,
    max_per_product_type_violation_count,
    seed_leakage_detected,
)
from productiq.recommendation.evaluation.diagnostics import observe_seed_failures
from productiq.recommendation.evaluation.metrics import (
    compute_relevance_metrics_at_k,
    macro_mean,
    recommendation_catalog_coverage,
    shortfall_metrics,
    unique_ratio,
)
from productiq.recommendation.evaluation.result_schema import (
    RecommendationAggregateMetrics,
    RecommendationBenchmarkEvaluationResult,
    RecommendationEvaluationConfig,
    RecommendationEvaluationLineage,
    RecommendationSeedMetrics,
    RecommendationVariantEvaluationResult,
)
from productiq.recommendation.selection_config import (
    RECOMMENDATION_SELECTION_CONFIG_VERSION,
    RecommendationSelectionConfig,
)
from productiq.recommendation.selection_context import RecommendationSelectionContext
from productiq.recommendation.selection_diagnostics import (
    RecommendationSelectionDiagnostic,
    RecommendationSelectionRejectionReason,
)
from productiq.recommendation.selection_keys import diversity_brand_key, diversity_product_type_key
from productiq.retrieval.evaluation.metrics import mean_reciprocal_rank


class RecommendationSeedPipelineSnapshot(BaseModel):
    """Observed pipeline outputs for one seed (evaluation input only)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    seed_product_id: str = Field(min_length=1)
    requested_top_k: int = Field(gt=0)
    candidate_pool_product_ids: tuple[str, ...] = ()
    ranked_recommendations: tuple[RankedRecommendation, ...] = ()
    final_recommendations: tuple[RankedRecommendation, ...] = ()
    selection_diagnostics: tuple[RecommendationSelectionDiagnostic, ...] = ()


def _grades_for_case(case: RecommendationBenchmarkCase) -> dict[str, int]:
    return {row.product_id: row.grade for row in case.relevance_judgments}


def _brand_keys_for_recommendations(
    recommendations: Sequence[RankedRecommendation],
    context: RecommendationSelectionContext | None,
) -> list[str | None]:
    if context is None:
        return [None for _ in recommendations]
    keys: list[str | None] = []
    for row in recommendations:
        filtering = context.filtering_by_product_id.get(row.product_id)
        product = context.product_by_product_id.get(row.product_id)
        keys.append(diversity_brand_key(filtering=filtering, product=product))
    return keys


def _product_type_keys_for_recommendations(
    recommendations: Sequence[RankedRecommendation],
    context: RecommendationSelectionContext | None,
) -> list[str | None]:
    if context is None:
        return [None for _ in recommendations]
    return [
        diversity_product_type_key(
            filtering=context.filtering_by_product_id.get(row.product_id),
            product=context.product_by_product_id.get(row.product_id),
        )
        for row in recommendations
    ]


def _relevant_dropped_by_constraint(
    *,
    case: RecommendationBenchmarkCase,
    snapshot: RecommendationSeedPipelineSnapshot,
    config: RecommendationEvaluationConfig,
) -> tuple[str, ...]:
    grades = _grades_for_case(case)
    relevant = {
        product_id
        for product_id, grade in grades.items()
        if grade >= config.min_relevant_grade
    }
    ranked_ids = {row.product_id for row in snapshot.ranked_recommendations}
    final_ids = {row.product_id for row in snapshot.final_recommendations}
    dropped = ranked_ids & relevant - final_ids
    if not dropped:
        return ()
    rejected: set[str] = set()
    for diagnostic in snapshot.selection_diagnostics:
        if (
            diagnostic.reason is not None
            and diagnostic.product_id in dropped
            and diagnostic.reason
            in {
                RecommendationSelectionRejectionReason.MAX_PER_BRAND,
                RecommendationSelectionRejectionReason.MAX_PER_PRODUCT_TYPE,
                RecommendationSelectionRejectionReason.FILTER_CONSTRAINT,
                RecommendationSelectionRejectionReason.SEED_EXCLUDED,
            }
        ):
            rejected.add(diagnostic.product_id)
    return tuple(sorted(rejected))


def evaluate_seed(
    case: RecommendationBenchmarkCase,
    snapshot: RecommendationSeedPipelineSnapshot,
    *,
    config: RecommendationEvaluationConfig,
    selection_context: RecommendationSelectionContext | None = None,
    selection_config: RecommendationSelectionConfig | None = None,
    use_final_recommendations: bool,
) -> RecommendationSeedMetrics:
    if case.seed_product_id != snapshot.seed_product_id:
        msg = "benchmark case seed_product_id must match pipeline snapshot"
        raise RecommendationError(msg)
    grades = _grades_for_case(case)
    recommendations = (
        snapshot.final_recommendations if use_final_recommendations else snapshot.ranked_recommendations
    )
    product_ids = tuple(row.product_id for row in recommendations)
    metrics_by_k = {
        k: compute_relevance_metrics_at_k(
            product_ids,
            grades,
            k=k,
            min_relevant_grade=config.min_relevant_grade,
        )
        for k in config.k_values
    }
    eval_metrics = compute_relevance_metrics_at_k(
        product_ids,
        grades,
        k=config.evaluation_top_k,
        min_relevant_grade=config.min_relevant_grade,
    )
    shortfall_count, shortfall_rate = shortfall_metrics(
        requested_top_k=snapshot.requested_top_k,
        returned_count=len(recommendations),
    )
    pool_coverage = candidate_coverage_ratio(
        judged_relevant_product_ids=tuple(
            product_id
            for product_id, grade in grades.items()
            if grade >= config.min_relevant_grade
        ),
        candidate_pool_product_ids=snapshot.candidate_pool_product_ids,
    )
    brand_keys = _brand_keys_for_recommendations(recommendations, selection_context)
    type_keys = _product_type_keys_for_recommendations(recommendations, selection_context)
    max_brand_violations = 0
    max_type_violations = 0
    if selection_config is not None and selection_context is not None:
        if selection_config.max_per_brand is not None:
            max_brand_violations = max_per_brand_violation_count(
                product_ids,
                context=selection_context,
                max_per_brand=selection_config.max_per_brand,
            )
        if selection_config.max_per_product_type is not None:
            max_type_violations = max_per_product_type_violation_count(
                product_ids,
                context=selection_context,
                max_per_product_type=selection_config.max_per_product_type,
            )
    observations = observe_seed_failures(
        relevance_grades=grades,
        min_relevant_grade=config.min_relevant_grade,
        requested_top_k=snapshot.requested_top_k,
        candidate_pool_product_ids=snapshot.candidate_pool_product_ids,
        ranked_product_ids=tuple(row.product_id for row in snapshot.ranked_recommendations),
        final_product_ids=product_ids,
        evaluation_k=config.evaluation_top_k,
        relevant_dropped_by_constraint_product_ids=_relevant_dropped_by_constraint(
            case=case,
            snapshot=snapshot,
            config=config,
        ),
    )
    return RecommendationSeedMetrics(
        seed_product_id=case.seed_product_id,
        requested_top_k=snapshot.requested_top_k,
        returned_count=len(recommendations),
        shortfall_count=shortfall_count,
        shortfall_rate=shortfall_rate,
        precision_at_k={k: metrics_by_k[k]["precision_at_k"] for k in config.k_values},
        recall_at_k={k: metrics_by_k[k]["recall_at_k"] for k in config.k_values},
        hit_rate_at_k={k: metrics_by_k[k]["hit_rate_at_k"] for k in config.k_values},
        ndcg_at_k={k: metrics_by_k[k]["ndcg_at_k"] for k in config.k_values},
        reciprocal_rank=eval_metrics["reciprocal_rank"],
        unique_brand_ratio=unique_ratio(brand_keys),
        unique_product_type_ratio=unique_ratio(type_keys),
        seed_leakage=seed_leakage_detected(
            seed_product_id=case.seed_product_id,
            recommendations=recommendations,
        ),
        duplicate_recommendation_count=duplicate_recommendation_count(recommendations),
        max_per_brand_violations=max_brand_violations,
        max_per_product_type_violations=max_type_violations,
        candidate_pool_coverage=pool_coverage,
        failure_observations=observations,
    )


def _aggregate_seed_metrics(
    per_seed: Sequence[RecommendationSeedMetrics],
    *,
    config: RecommendationEvaluationConfig,
    eligible_catalog_product_count: int | None,
    all_recommended_product_ids: Sequence[str],
) -> RecommendationAggregateMetrics:
    if not per_seed:
        msg = "cannot aggregate empty seed metrics"
        raise RecommendationError(msg)
    mean_precision = {
        k: macro_mean(tuple(row.precision_at_k[k] for row in per_seed)) for k in config.k_values
    }
    recall_values_by_k: dict[int, list[float]] = {k: [] for k in config.k_values}
    ndcg_values_by_k: dict[int, list[float]] = {k: [] for k in config.k_values}
    for row in per_seed:
        for k in config.k_values:
            recall_value = row.recall_at_k[k]
            if recall_value is not None:
                recall_values_by_k[k].append(recall_value)
            ndcg_value = row.ndcg_at_k[k]
            if ndcg_value is not None:
                ndcg_values_by_k[k].append(ndcg_value)
    mean_recall = {
        k: macro_mean(tuple(recall_values_by_k[k])) if recall_values_by_k[k] else 0.0
        for k in config.k_values
    }
    mean_ndcg = {
        k: macro_mean(tuple(ndcg_values_by_k[k])) if ndcg_values_by_k[k] else 0.0
        for k in config.k_values
    }
    return RecommendationAggregateMetrics(
        seed_count=len(per_seed),
        mean_precision_at_k=mean_precision,
        mean_recall_at_k=mean_recall,
        recall_aggregate_seed_count=min(len(recall_values_by_k[k]) for k in config.k_values),
        mean_hit_rate_at_k={
            k: macro_mean(tuple(row.hit_rate_at_k[k] for row in per_seed)) for k in config.k_values
        },
        mean_ndcg_at_k=mean_ndcg,
        ndcg_aggregate_seed_count=min(len(ndcg_values_by_k[k]) for k in config.k_values),
        mrr=mean_reciprocal_rank(tuple(row.reciprocal_rank for row in per_seed)),
        mean_shortfall_rate=macro_mean(tuple(row.shortfall_rate for row in per_seed)),
        seed_leakage_rate=sum(1 for row in per_seed if row.seed_leakage) / len(per_seed),
        duplicate_recommendation_rate=sum(
            1 for row in per_seed if row.duplicate_recommendation_count > 0
        )
        / len(per_seed),
        recommendation_catalog_coverage=recommendation_catalog_coverage(
            all_recommended_product_ids,
            eligible_catalog_product_count=eligible_catalog_product_count,
        )
        if eligible_catalog_product_count is not None
        else None,
        k_values=config.k_values,
    )


def evaluate_variant(
    benchmark: RecommendationBenchmark,
    snapshots_by_seed: Mapping[str, RecommendationSeedPipelineSnapshot],
    *,
    config: RecommendationEvaluationConfig,
    variant_name: str,
    use_final_recommendations: bool,
    ranker_version: str | None = BASELINE_RECOMMENDATION_RANKER_VERSION,
    selection_version: str | None = None,
    selection_context: RecommendationSelectionContext | None = None,
    selection_config: RecommendationSelectionConfig | None = None,
) -> RecommendationVariantEvaluationResult:
    per_seed_rows: list[RecommendationSeedMetrics] = []
    all_product_ids: list[str] = []
    for case in sorted(benchmark.cases, key=lambda row: row.seed_product_id):
        snapshot = snapshots_by_seed.get(case.seed_product_id)
        if snapshot is None:
            msg = f"missing pipeline snapshot for seed {case.seed_product_id!r}"
            raise RecommendationError(msg)
        row = evaluate_seed(
            case,
            snapshot,
            config=config,
            selection_context=selection_context,
            selection_config=selection_config,
            use_final_recommendations=use_final_recommendations,
        )
        per_seed_rows.append(row)
        recommendations = (
            snapshot.final_recommendations
            if use_final_recommendations
            else snapshot.ranked_recommendations
        )
        all_product_ids.extend(item.product_id for item in recommendations)
    per_seed = tuple(per_seed_rows)
    aggregate = _aggregate_seed_metrics(
        per_seed,
        config=config,
        eligible_catalog_product_count=benchmark.metadata.eligible_catalog_product_count,
        all_recommended_product_ids=tuple(dict.fromkeys(all_product_ids)),
    )
    lineage = RecommendationEvaluationLineage(
        benchmark_name=benchmark.metadata.benchmark_name,
        benchmark_version=benchmark.metadata.benchmark_version,
        variant_name=variant_name,
        ranker_version=ranker_version,
        selection_version=selection_version,
        evaluation_top_k=config.evaluation_top_k,
        k_values=config.k_values,
        min_relevant_grade=config.min_relevant_grade,
        catalog_artifact=benchmark.metadata.catalog_artifact,
        source_representation_checksum=benchmark.metadata.source_representation_checksum,
    )
    return RecommendationVariantEvaluationResult(
        lineage=lineage,
        per_seed=per_seed,
        aggregate=aggregate,
    )


def evaluate_recommendation_benchmark(
    benchmark: RecommendationBenchmark,
    snapshots_by_seed: Mapping[str, RecommendationSeedPipelineSnapshot],
    *,
    config: RecommendationEvaluationConfig | None = None,
    selection_context: RecommendationSelectionContext | None = None,
    selection_config: RecommendationSelectionConfig | None = None,
) -> RecommendationBenchmarkEvaluationResult:
    resolved = config or RecommendationEvaluationConfig()
    baseline = evaluate_variant(
        benchmark,
        snapshots_by_seed,
        config=resolved,
        variant_name=RECOMMENDATION_VARIANT_BASELINE_11_5,
        use_final_recommendations=False,
        selection_version=None,
    )
    with_selection = evaluate_variant(
        benchmark,
        snapshots_by_seed,
        config=resolved,
        variant_name=RECOMMENDATION_VARIANT_BASELINE_11_5_PLUS_SELECTION_11_6,
        use_final_recommendations=True,
        selection_version=RECOMMENDATION_SELECTION_CONFIG_VERSION,
        selection_context=selection_context,
        selection_config=selection_config,
    )
    comparison = compare_recommendation_variants(baseline, with_selection)
    return RecommendationBenchmarkEvaluationResult(
        benchmark_name=benchmark.metadata.benchmark_name,
        benchmark_version=benchmark.metadata.benchmark_version,
        seed_count=len(benchmark.cases),
        config=resolved,
        baseline=baseline,
        with_selection=with_selection,
        comparison=comparison,
    )


__all__ = [
    "RecommendationSeedPipelineSnapshot",
    "evaluate_recommendation_benchmark",
    "evaluate_seed",
    "evaluate_variant",
]
