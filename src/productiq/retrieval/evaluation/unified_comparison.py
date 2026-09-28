"""Compare unified retrieval evaluation runs (Phase 4.18)."""

from __future__ import annotations

from productiq.retrieval.evaluation.unified_evaluation_schema import (
    EvaluationComparisonResult,
    EvaluationResult,
    MetricDelta,
)


def _metric_delta(baseline: float, comparison: float) -> MetricDelta:
    absolute = comparison - baseline
    relative = None
    if baseline != 0.0:
        relative = absolute / baseline
    return MetricDelta(absolute_delta=absolute, relative_delta=relative)


def compatibility_reasons(
    baseline: EvaluationResult,
    comparison: EvaluationResult,
) -> tuple[str, ...]:
    reasons: list[str] = []
    left = baseline.lineage
    right = comparison.lineage
    if left.benchmark_name != right.benchmark_name:
        reasons.append(
            f"benchmark_name mismatch: {left.benchmark_name!r} vs {right.benchmark_name!r}"
        )
    if left.benchmark_version != right.benchmark_version:
        reasons.append(
            f"benchmark_version mismatch: {left.benchmark_version!r} vs {right.benchmark_version!r}"
        )
    if left.retrieval_top_k != right.retrieval_top_k:
        reasons.append(
            f"retrieval_top_k mismatch: {left.retrieval_top_k} vs {right.retrieval_top_k}"
        )
    if left.k_values != right.k_values:
        reasons.append(f"k_values mismatch: {left.k_values} vs {right.k_values}")
    if len(baseline.per_query) != len(comparison.per_query):
        reasons.append("per_query count mismatch")
    return tuple(reasons)


def compare_evaluation_results(
    baseline: EvaluationResult,
    comparison: EvaluationResult,
) -> EvaluationComparisonResult:
    """Compare aggregate metrics without declaring a winner."""
    reasons = compatibility_reasons(baseline, comparison)
    compatible = not reasons
    limitations = (
        "Comparison reports metric deltas only; it does not rank systems or recommend changes.",
    )
    if not compatible:
        return EvaluationComparisonResult(
            compatible=False,
            incompatibility_reasons=reasons,
            baseline_system_name=baseline.lineage.system_name,
            comparison_system_name=comparison.lineage.system_name,
            baseline_lineage=baseline.lineage,
            comparison_lineage=comparison.lineage,
            precision_at_k_deltas={},
            recall_at_k_deltas={},
            mrr_delta=MetricDelta(absolute_delta=0.0, relative_delta=None),
            limitations=limitations,
        )

    k_values = baseline.lineage.k_values
    precision_deltas: dict[int, MetricDelta] = {}
    recall_deltas: dict[int, MetricDelta] = {}
    for k in k_values:
        precision_deltas[k] = _metric_delta(
            baseline.aggregate.mean_precision_at_k[k],
            comparison.aggregate.mean_precision_at_k[k],
        )
        recall_deltas[k] = _metric_delta(
            baseline.aggregate.mean_recall_at_k[k],
            comparison.aggregate.mean_recall_at_k[k],
        )
    mrr_delta = _metric_delta(baseline.aggregate.mrr, comparison.aggregate.mrr)
    extra_limits: list[str] = []
    if baseline.lineage.rrf_bm25_index_mode or comparison.lineage.rrf_bm25_index_mode:
        extra_limits.append(
            "RRF or hybrid lineage may include scoped BM25; cross-system deltas are "
            "descriptive only when retrieval configurations differ."
        )
    return EvaluationComparisonResult(
        compatible=True,
        incompatibility_reasons=(),
        baseline_system_name=baseline.lineage.system_name,
        comparison_system_name=comparison.lineage.system_name,
        baseline_lineage=baseline.lineage,
        comparison_lineage=comparison.lineage,
        precision_at_k_deltas=precision_deltas,
        recall_at_k_deltas=recall_deltas,
        mrr_delta=mrr_delta,
        limitations=limitations + tuple(extra_limits),
    )


__all__ = ["compare_evaluation_results", "compatibility_reasons"]
