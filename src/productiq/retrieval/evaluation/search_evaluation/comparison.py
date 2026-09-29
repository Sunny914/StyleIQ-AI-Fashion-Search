"""Compare search evaluation variant results (Phase 12.1)."""

from __future__ import annotations

from productiq.exceptions.base import LexicalRetrievalError
from productiq.retrieval.evaluation.search_evaluation.result_schema import (
    SearchExperimentComparison,
    SearchVariantEvaluationResult,
)


def compare_search_evaluation_variants(
    baseline: SearchVariantEvaluationResult,
    comparison: SearchVariantEvaluationResult,
) -> SearchExperimentComparison:
    """Report aggregate metric deltas without ranking variants."""
    left = baseline.lineage
    right = comparison.lineage
    if (
        left.benchmark_name != right.benchmark_name
        or left.benchmark_version != right.benchmark_version
    ):
        msg = "benchmark identity must match for comparison"
        raise LexicalRetrievalError(msg)
    k_values = baseline.aggregate.k_values
    if comparison.aggregate.k_values != k_values:
        msg = "aggregate k_values must match for comparison"
        raise LexicalRetrievalError(msg)
    if left.metric_configuration != right.metric_configuration:
        msg = "metric_configuration must match for comparison"
        raise LexicalRetrievalError(msg)
    return SearchExperimentComparison(
        benchmark_name=left.benchmark_name,
        benchmark_version=left.benchmark_version,
        baseline_variant=left.variant_name,
        comparison_variant=right.variant_name,
        precision_at_k_delta={
            k: comparison.aggregate.mean_precision_at_k[k]
            - baseline.aggregate.mean_precision_at_k[k]
            for k in k_values
        },
        recall_at_k_delta={
            k: comparison.aggregate.mean_recall_at_k[k] - baseline.aggregate.mean_recall_at_k[k]
            for k in k_values
        },
        hit_rate_at_k_delta={
            k: comparison.aggregate.mean_hit_rate_at_k[k] - baseline.aggregate.mean_hit_rate_at_k[k]
            for k in k_values
        },
        ndcg_at_k_delta={
            k: comparison.aggregate.mean_ndcg_at_k[k] - baseline.aggregate.mean_ndcg_at_k[k]
            for k in k_values
        },
        mrr_delta=comparison.aggregate.mrr - baseline.aggregate.mrr,
    )


__all__ = ["compare_search_evaluation_variants"]
