"""Compare baseline vs LTR aggregate metrics (Phase 10.8)."""

from __future__ import annotations

from productiq.ranking.ltr.comparison.schema import (
    BaselineLTRMetricComparisonValue,
    BaselineLTRRankingComparison,
)
from productiq.retrieval.evaluation.unified_evaluation_schema import EvaluationMetrics


def _triple(baseline: float, ltr: float) -> BaselineLTRMetricComparisonValue:
    return BaselineLTRMetricComparisonValue(baseline=baseline, ltr=ltr, delta=ltr - baseline)


def compare_baseline_ltr_metrics(
    *,
    baseline: EvaluationMetrics,
    ltr: EvaluationMetrics,
    k_values: tuple[int, ...],
) -> BaselineLTRRankingComparison:
    if baseline.k_values != ltr.k_values:
        msg = "baseline and LTR metric k_values must match"
        raise ValueError(msg)
    precision: dict[int, BaselineLTRMetricComparisonValue] = {}
    recall: dict[int, BaselineLTRMetricComparisonValue] = {}
    for k in k_values:
        precision[k] = _triple(
            baseline.mean_precision_at_k[k],
            ltr.mean_precision_at_k[k],
        )
        recall[k] = _triple(
            baseline.mean_recall_at_k[k],
            ltr.mean_recall_at_k[k],
        )
    return BaselineLTRRankingComparison(
        mrr=_triple(baseline.mrr, ltr.mrr),
        precision_at_k=precision,
        recall_at_k=recall,
    )


__all__ = ["compare_baseline_ltr_metrics"]
