"""Compare recommendation evaluation variants (Phase 11.7)."""

from __future__ import annotations

from productiq.exceptions.base import RecommendationError
from productiq.recommendation.evaluation.result_schema import (
    RecommendationEvaluationComparison,
    RecommendationVariantEvaluationResult,
)


def compare_recommendation_variants(
    baseline: RecommendationVariantEvaluationResult,
    comparison: RecommendationVariantEvaluationResult,
) -> RecommendationEvaluationComparison:
    k_values = baseline.aggregate.k_values
    if comparison.aggregate.k_values != k_values:
        msg = "variant k_values must match for comparison"
        raise RecommendationError(msg)
    return RecommendationEvaluationComparison(
        baseline_variant=baseline.lineage.variant_name,
        comparison_variant=comparison.lineage.variant_name,
        precision_at_k_delta={
            k: comparison.aggregate.mean_precision_at_k[k] - baseline.aggregate.mean_precision_at_k[k]
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
        mrr_delta=comparison.aggregate.mrr - baseline.aggregate.mrr,
        mean_shortfall_rate_delta=(
            comparison.aggregate.mean_shortfall_rate - baseline.aggregate.mean_shortfall_rate
        ),
    )


__all__ = ["compare_recommendation_variants"]
