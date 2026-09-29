"""Cross-artifact invariants for Phase 12 evaluation hardening (12.11)."""

from __future__ import annotations

from productiq.exceptions.base import RetrievalError
from productiq.retrieval.evaluation.search_evaluation.baseline_schema import (
    SEARCH_BASELINE_BM25_VARIANT_NAME,
    SEARCH_BASELINE_RRF_VARIANT_NAME,
    SEARCH_BASELINE_SEMANTIC_VARIANT_NAME,
)
from productiq.retrieval.evaluation.search_evaluation.experiment_validation import (
    validate_shared_evaluation_envelope,
)
from productiq.retrieval.evaluation.search_evaluation.ranking_experiment_schema import (
    SEARCH_RANKING_VARIANT_BASELINE_RANKER,
    SEARCH_RANKING_VARIANT_LTR,
    SEARCH_RANKING_VARIANT_RETRIEVAL_ORDER,
)
from productiq.retrieval.evaluation.search_evaluation.reporting.report_loader import (
    SearchEvaluationReportSources,
)
from productiq.retrieval.evaluation.search_evaluation.request_schema import (
    SearchMetricConfiguration,
)


def validate_benchmark_query_identity(sources: SearchEvaluationReportSources) -> None:
    expected = {query.query_id for query in sources.benchmark.queries}
    if len(expected) != len(sources.benchmark.queries):
        msg = "benchmark contains duplicate query_id values"
        raise RetrievalError(msg)
    for bundle in sources.baselines:
        observed = {row.query_id for row in bundle.evaluation_result.per_query}
        if observed != expected:
            missing = sorted(expected - observed)
            extra = sorted(observed - expected)
            msg = (
                f"baseline {bundle.evaluation_result.lineage.variant_name!r} query_id set "
                f"must match benchmark exactly; missing={missing!r} extra={extra!r}"
            )
            raise RetrievalError(msg)


def validate_metric_configuration_identity(
    left: SearchMetricConfiguration,
    right: SearchMetricConfiguration,
    *,
    label: str,
) -> None:
    if left.model_dump() != right.model_dump():
        msg = f"{label} metric_configuration incompatible with canonical envelope"
        raise RetrievalError(msg)


def validate_execution_depth_consistency(sources: SearchEvaluationReportSources) -> None:
    envelope = validate_shared_evaluation_envelope(
        [row.evaluation_result for row in sources.baselines]
    )
    for bundle in sources.baselines:
        config = bundle.payload.get("execution_configuration")
        if not isinstance(config, dict):
            continue
        execution_top_k = config.get("execution_top_k")
        evaluation_top_k = config.get("evaluation_top_k")
        if execution_top_k != envelope.metric_configuration.execution_top_k:
            msg = (
                f"baseline {bundle.evaluation_result.lineage.variant_name!r} "
                f"execution_top_k mismatch"
            )
            raise RetrievalError(msg)
        if evaluation_top_k != envelope.metric_configuration.evaluation_top_k:
            msg = (
                f"baseline {bundle.evaluation_result.lineage.variant_name!r} "
                f"evaluation_top_k mismatch"
            )
            raise RetrievalError(msg)


def validate_canonical_statistical_comparison_pairs(sources: SearchEvaluationReportSources) -> None:
    if sources.statistical_analysis is None:
        return
    expected = {
        (SEARCH_BASELINE_BM25_VARIANT_NAME, SEARCH_BASELINE_SEMANTIC_VARIANT_NAME),
        (SEARCH_BASELINE_BM25_VARIANT_NAME, SEARCH_BASELINE_RRF_VARIANT_NAME),
        (SEARCH_RANKING_VARIANT_RETRIEVAL_ORDER, SEARCH_RANKING_VARIANT_BASELINE_RANKER),
        (SEARCH_RANKING_VARIANT_RETRIEVAL_ORDER, SEARCH_RANKING_VARIANT_LTR),
    }
    configured = {
        (row.reference_variant_name, row.candidate_variant_name)
        for row in sources.statistical_analysis.configuration.comparison_pairs
    }
    reverse_redundant = {
        (SEARCH_BASELINE_RRF_VARIANT_NAME, SEARCH_BASELINE_BM25_VARIANT_NAME),
    }
    if reverse_redundant & configured:
        msg = "redundant reverse statistical comparison pair detected (RRF -> BM25)"
        raise RetrievalError(msg)
    missing = expected - configured
    if missing:
        msg = f"canonical statistical comparison pairs missing from configuration: {sorted(missing)!r}"
        raise RetrievalError(msg)


def validate_cross_artifact_invariants(sources: SearchEvaluationReportSources) -> None:
    validate_benchmark_query_identity(sources)
    validate_execution_depth_consistency(sources)
    validate_canonical_statistical_comparison_pairs(sources)


__all__ = [
    "validate_benchmark_query_identity",
    "validate_canonical_statistical_comparison_pairs",
    "validate_cross_artifact_invariants",
    "validate_execution_depth_consistency",
    "validate_metric_configuration_identity",
]
