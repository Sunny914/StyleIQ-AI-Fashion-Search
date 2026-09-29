"""Search evaluation metric computation (Phase 12.3)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from productiq.exceptions.base import RetrievalError
from productiq.recommendation.evaluation.metrics import (
    hit_rate_at_k,
    judged_relevant_product_ids,
    ndcg_at_k,
)
from productiq.retrieval.evaluation.metrics import (
    macro_mean,
    mean_reciprocal_rank,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
    validate_positive_k,
)
from productiq.retrieval.evaluation.search_evaluation.benchmark_schema import (
    SearchEvaluationBenchmark,
    SearchEvaluationQuery,
)
from productiq.retrieval.evaluation.search_evaluation.request_schema import (
    SearchEvaluationVariant,
    SearchMetricConfiguration,
    SearchRankedResultsForQuery,
)
from productiq.retrieval.evaluation.search_evaluation.result_schema import (
    SearchAggregateMetricResult,
    SearchEvaluationLineage,
    SearchQueryMetricResult,
    SearchVariantEvaluationResult,
)
from productiq.retrieval.evaluation.search_evaluation.schema import (
    MAX_SEARCH_RELEVANCE_GRADE,
    MIN_SEARCH_RELEVANCE_GRADE,
)


def validate_search_ranked_product_ids(ranked_product_ids: Sequence[str]) -> tuple[str, ...]:
    """Reject empty IDs and duplicate ranks (no silent deduplication)."""
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in ranked_product_ids:
        product_id = str(raw).strip()
        if not product_id:
            msg = "ranked product_id must not be empty"
            raise RetrievalError(msg)
        if product_id in seen:
            msg = f"duplicate ranked product_id {product_id!r}"
            raise RetrievalError(msg)
        seen.add(product_id)
        normalized.append(product_id)
    return tuple(normalized)


def relevance_grades_from_query(query: SearchEvaluationQuery) -> dict[str, int]:
    return {judgment.product_id: judgment.grade for judgment in query.relevance_judgments}


def validate_search_relevance_grades(grades: Mapping[str, int]) -> None:
    for product_id, grade in grades.items():
        if not product_id.strip():
            msg = "relevance grade product_id must not be empty"
            raise RetrievalError(msg)
        if grade < MIN_SEARCH_RELEVANCE_GRADE or grade > MAX_SEARCH_RELEVANCE_GRADE:
            msg = (
                f"relevance grade must be in "
                f"[{MIN_SEARCH_RELEVANCE_GRADE}, {MAX_SEARCH_RELEVANCE_GRADE}]"
            )
            raise RetrievalError(msg)


def evaluation_ranked_prefix(
    ranked_product_ids: Sequence[str],
    *,
    evaluation_top_k: int,
) -> tuple[str, ...]:
    validate_positive_k(evaluation_top_k)
    ranked = validate_search_ranked_product_ids(ranked_product_ids)
    return ranked[:evaluation_top_k]


def compute_search_query_metrics(
    query: SearchEvaluationQuery,
    ranked_product_ids: Sequence[str],
    metric_configuration: SearchMetricConfiguration,
) -> SearchQueryMetricResult:
    """Compute per-query metrics from ranked IDs and curated judgments only."""
    evaluated_ranked = evaluation_ranked_prefix(
        ranked_product_ids,
        evaluation_top_k=metric_configuration.evaluation_top_k,
    )
    grades = relevance_grades_from_query(query)
    validate_search_relevance_grades(grades)
    relevant = judged_relevant_product_ids(
        grades,
        min_relevant_grade=metric_configuration.min_relevant_grade,
    )
    recall_eligible = len(relevant) > 0

    precision_map: dict[int, float] = {}
    recall_map: dict[int, float | None] = {}
    hit_rate_map: dict[int, float] = {}
    ndcg_map: dict[int, float | None] = {}

    for k in metric_configuration.k_values:
        precision_map[k] = precision_at_k(evaluated_ranked, relevant, k=k)
        recall_map[k] = recall_at_k(evaluated_ranked, relevant, k=k)
        hit_rate_map[k] = hit_rate_at_k(
            evaluated_ranked,
            grades,
            k=k,
            min_relevant_grade=metric_configuration.min_relevant_grade,
        )
        if metric_configuration.compute_ndcg:
            ndcg_map[k] = ndcg_at_k(evaluated_ranked, grades, k=k)

    reciprocal_rank_value = reciprocal_rank(evaluated_ranked, relevant)[0]

    return SearchQueryMetricResult(
        query_id=query.query_id,
        query_text=query.query_text,
        query_category=query.query_category,
        judged_relevant_count=len(relevant),
        ranked_product_ids=evaluated_ranked,
        precision_at_k=precision_map,
        recall_at_k=recall_map,
        hit_rate_at_k=hit_rate_map,
        ndcg_at_k=ndcg_map,
        reciprocal_rank=reciprocal_rank_value,
        recall_aggregate_eligible=recall_eligible,
    )


def aggregate_search_query_metrics(
    per_query: Sequence[SearchQueryMetricResult],
    metric_configuration: SearchMetricConfiguration,
) -> SearchAggregateMetricResult:
    if not per_query:
        msg = "cannot aggregate empty search query metrics"
        raise RetrievalError(msg)

    k_values = metric_configuration.k_values
    mean_precision = {
        k: macro_mean(tuple(row.precision_at_k[k] for row in per_query)) for k in k_values
    }
    mean_hit_rate = {
        k: macro_mean(tuple(row.hit_rate_at_k[k] for row in per_query)) for k in k_values
    }

    recall_values_by_k: dict[int, list[float]] = {k: [] for k in k_values}
    for row in per_query:
        if not row.recall_aggregate_eligible:
            continue
        for k in k_values:
            recall_value = row.recall_at_k[k]
            if recall_value is not None:
                recall_values_by_k[k].append(recall_value)
    mean_recall = {
        k: macro_mean(tuple(recall_values_by_k[k])) if recall_values_by_k[k] else 0.0
        for k in k_values
    }
    recall_aggregate_query_count = sum(1 for row in per_query if row.recall_aggregate_eligible)

    mean_ndcg: dict[int, float] = {k: 0.0 for k in k_values}
    ndcg_aggregate_query_count = 0
    if metric_configuration.compute_ndcg:
        ndcg_values_by_k: dict[int, list[float]] = {k: [] for k in k_values}
        for row in per_query:
            for k in k_values:
                ndcg_value = row.ndcg_at_k.get(k)
                if ndcg_value is not None:
                    ndcg_values_by_k[k].append(ndcg_value)
        mean_ndcg = {
            k: macro_mean(tuple(ndcg_values_by_k[k])) if ndcg_values_by_k[k] else 0.0
            for k in k_values
        }
        if ndcg_values_by_k[k_values[0]]:
            ndcg_aggregate_query_count = min(len(ndcg_values_by_k[k]) for k in k_values)
        else:
            ndcg_aggregate_query_count = 0

    mrr = mean_reciprocal_rank(tuple(row.reciprocal_rank for row in per_query))

    return SearchAggregateMetricResult(
        query_count=len(per_query),
        recall_aggregate_query_count=recall_aggregate_query_count,
        ndcg_aggregate_query_count=ndcg_aggregate_query_count,
        k_values=k_values,
        mean_precision_at_k=mean_precision,
        mean_recall_at_k=mean_recall,
        mean_hit_rate_at_k=mean_hit_rate,
        mean_ndcg_at_k=mean_ndcg,
        mrr=mrr,
    )


def _ranked_results_index(
    ranked_results: Sequence[SearchRankedResultsForQuery],
) -> dict[str, tuple[str, ...]]:
    index: dict[str, tuple[str, ...]] = {}
    for row in ranked_results:
        if row.query_id in index:
            msg = f"duplicate ranked results for query_id {row.query_id!r}"
            raise RetrievalError(msg)
        index[row.query_id] = validate_search_ranked_product_ids(row.ranked_product_ids)
    return index


def evaluate_search_variant_metrics(
    benchmark: SearchEvaluationBenchmark,
    variant: SearchEvaluationVariant,
    ranked_results: Sequence[SearchRankedResultsForQuery],
    *,
    metric_configuration: SearchMetricConfiguration | None = None,
) -> SearchVariantEvaluationResult:
    """Compute search metrics for one variant (ranked IDs supplied; no search execution)."""
    config = metric_configuration or SearchMetricConfiguration()
    ranked_by_query_id = _ranked_results_index(ranked_results)
    expected_ids = {query.query_id for query in benchmark.queries}
    missing = expected_ids - ranked_by_query_id.keys()
    if missing:
        sample = sorted(missing)[:5]
        msg = f"missing ranked results for benchmark queries: {sample}"
        raise RetrievalError(msg)
    extra = ranked_by_query_id.keys() - expected_ids
    if extra:
        sample = sorted(extra)[:5]
        msg = f"unexpected ranked results for unknown query_id values: {sample}"
        raise RetrievalError(msg)

    per_query_rows: list[SearchQueryMetricResult] = []
    for query in sorted(benchmark.queries, key=lambda row: row.query_id):
        per_query_rows.append(
            compute_search_query_metrics(
                query,
                ranked_by_query_id[query.query_id],
                config,
            )
        )

    aggregate = aggregate_search_query_metrics(per_query_rows, config)
    lineage = SearchEvaluationLineage(
        benchmark_name=benchmark.benchmark_name,
        benchmark_version=benchmark.benchmark_version,
        variant_name=variant.variant_name,
        variant_version=variant.variant_version,
        metric_configuration=config,
        catalog_artifact=benchmark.metadata.catalog_artifact,
        source_representation_checksum=benchmark.metadata.source_representation_checksum,
        variant_lineage_labels=variant.lineage_labels,
    )
    return SearchVariantEvaluationResult(
        lineage=lineage,
        per_query=tuple(per_query_rows),
        aggregate=aggregate,
    )


__all__ = [
    "aggregate_search_query_metrics",
    "compute_search_query_metrics",
    "evaluate_search_variant_metrics",
    "evaluation_ranked_prefix",
    "relevance_grades_from_query",
    "validate_search_ranked_product_ids",
    "validate_search_relevance_grades",
]
