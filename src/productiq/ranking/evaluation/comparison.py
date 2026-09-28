"""Compare RRF-order vs baseline ranking metrics (Phase 10.6)."""

from __future__ import annotations

from productiq.ranking.evaluation.schema import MetricComparisonValue, RankingEvaluationComparison
from productiq.retrieval.evaluation.unified_evaluation_schema import EvaluationMetrics


def _triple(rrf: float, baseline: float) -> MetricComparisonValue:
    return MetricComparisonValue(rrf=rrf, baseline=baseline, delta=baseline - rrf)


def compare_ranking_evaluation_metrics(
    *,
    rrf: EvaluationMetrics,
    baseline: EvaluationMetrics,
    k_values: tuple[int, ...],
) -> RankingEvaluationComparison:
    if rrf.k_values != baseline.k_values:
        msg = "RRF and baseline metric k_values must match"
        raise ValueError(msg)
    precision: dict[int, MetricComparisonValue] = {}
    recall: dict[int, MetricComparisonValue] = {}
    for k in k_values:
        precision[k] = _triple(
            rrf.mean_precision_at_k[k],
            baseline.mean_precision_at_k[k],
        )
        recall[k] = _triple(
            rrf.mean_recall_at_k[k],
            baseline.mean_recall_at_k[k],
        )
    return RankingEvaluationComparison(
        mrr=_triple(rrf.mrr, baseline.mrr),
        precision_at_k=precision,
        recall_at_k=recall,
    )


__all__ = ["compare_ranking_evaluation_metrics"]
