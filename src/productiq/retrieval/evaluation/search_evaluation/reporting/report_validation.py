"""Validate Phase 12 artifact compatibility for reporting (Phase 12.10)."""

from __future__ import annotations

from productiq.exceptions.base import RetrievalError
from productiq.retrieval.evaluation.search_evaluation.baseline_schema import (
    SEARCH_BASELINE_ARTIFACT_SCHEMA_VERSION,
)
from productiq.retrieval.evaluation.search_evaluation.benchmark_artifact_schema import (
    SEARCH_BENCHMARK_ARTIFACT_SCHEMA_VERSION,
)
from productiq.retrieval.evaluation.search_evaluation.experiment_schema import (
    SEARCH_EXPERIMENT_ARTIFACT_SCHEMA_VERSION,
)
from productiq.retrieval.evaluation.search_evaluation.experiment_validation import (
    validate_shared_evaluation_envelope,
)
from productiq.retrieval.evaluation.search_evaluation.failure_analysis_schema import (
    SEARCH_FAILURE_ANALYSIS_ARTIFACT_SCHEMA_VERSION,
)
from productiq.retrieval.evaluation.search_evaluation.ranking_experiment_schema import (
    SEARCH_RANKING_EXPERIMENT_ARTIFACT_SCHEMA_VERSION,
)
from productiq.retrieval.evaluation.search_evaluation.reporting.report_loader import (
    SearchEvaluationReportSources,
)
from productiq.retrieval.evaluation.search_evaluation.statistical_schema import (
    SEARCH_STATISTICAL_ANALYSIS_ARTIFACT_SCHEMA_VERSION,
)


def _require_schema_version(payload: dict[str, object], expected: str, label: str) -> None:
    actual = payload.get("artifact_schema_version")
    if actual != expected:
        msg = f"{label} artifact_schema_version {actual!r} != expected {expected!r}"
        raise RetrievalError(msg)


def validate_report_sources(sources: SearchEvaluationReportSources) -> None:
    benchmark_meta = sources.benchmark.metadata
    _require_schema_version(
        sources.benchmark_payload,
        SEARCH_BENCHMARK_ARTIFACT_SCHEMA_VERSION,
        "benchmark",
    )

    baseline_results = [row.evaluation_result for row in sources.baselines]
    envelope = validate_shared_evaluation_envelope(baseline_results)
    if (
        envelope.benchmark_name != benchmark_meta.benchmark_name
        or envelope.benchmark_version != benchmark_meta.benchmark_version
    ):
        msg = "baseline artifacts benchmark identity must match canonical benchmark artifact"
        raise RetrievalError(msg)

    seen_variants: set[str] = set()
    for bundle in sources.baselines:
        _require_schema_version(
            bundle.payload, SEARCH_BASELINE_ARTIFACT_SCHEMA_VERSION, "12.5 baseline"
        )
        name = bundle.evaluation_result.lineage.variant_name
        if name in seen_variants:
            msg = f"duplicate baseline variant_name {name!r}"
            raise RetrievalError(msg)
        seen_variants.add(name)
        if bundle.evaluation_result.lineage.metric_configuration != envelope.metric_configuration:
            msg = f"baseline {name!r} metric_configuration incompatible with shared envelope"
            raise RetrievalError(msg)

    if sources.baseline_experiment is not None:
        assert sources.baseline_experiment_payload is not None
        _require_schema_version(
            sources.baseline_experiment_payload,
            SEARCH_EXPERIMENT_ARTIFACT_SCHEMA_VERSION,
            "12.6 experiment",
        )
        exp_env = sources.baseline_experiment.envelope
        if (
            exp_env.benchmark_name != envelope.benchmark_name
            or exp_env.benchmark_version != envelope.benchmark_version
        ):
            msg = "12.6 experiment benchmark identity mismatch"
            raise RetrievalError(msg)
        if exp_env.metric_configuration != envelope.metric_configuration:
            msg = "12.6 experiment metric_configuration mismatch"
            raise RetrievalError(msg)
        if exp_env.catalog_artifact != envelope.catalog_artifact:
            msg = "12.6 experiment catalog_artifact mismatch"
            raise RetrievalError(msg)
        if exp_env.source_representation_checksum != envelope.source_representation_checksum:
            msg = "12.6 experiment source_representation_checksum mismatch"
            raise RetrievalError(msg)

    if sources.ranking_experiment is not None:
        assert sources.ranking_experiment_payload is not None
        _require_schema_version(
            sources.ranking_experiment_payload,
            SEARCH_RANKING_EXPERIMENT_ARTIFACT_SCHEMA_VERSION,
            "12.7 ranking",
        )
        rank_env = sources.ranking_experiment.envelope
        if (
            rank_env.benchmark_name != envelope.benchmark_name
            or rank_env.benchmark_version != envelope.benchmark_version
        ):
            msg = "12.7 ranking experiment benchmark identity mismatch"
            raise RetrievalError(msg)
        if rank_env.metric_configuration != envelope.metric_configuration:
            msg = "12.7 ranking experiment metric_configuration mismatch"
            raise RetrievalError(msg)

    if sources.failure_analysis is not None:
        assert sources.failure_analysis_payload is not None
        _require_schema_version(
            sources.failure_analysis_payload,
            SEARCH_FAILURE_ANALYSIS_ARTIFACT_SCHEMA_VERSION,
            "12.8 failure analysis",
        )
        failure_lineage = sources.failure_analysis.lineage
        if (
            failure_lineage.benchmark_name != envelope.benchmark_name
            or failure_lineage.benchmark_version != envelope.benchmark_version
        ):
            msg = "12.8 failure analysis benchmark identity mismatch"
            raise RetrievalError(msg)

    if sources.statistical_analysis is not None:
        assert sources.statistical_analysis_payload is not None
        _require_schema_version(
            sources.statistical_analysis_payload,
            SEARCH_STATISTICAL_ANALYSIS_ARTIFACT_SCHEMA_VERSION,
            "12.9 statistical analysis",
        )
        statistical_lineage = sources.statistical_analysis.lineage
        if (
            statistical_lineage.benchmark_name != envelope.benchmark_name
            or statistical_lineage.benchmark_version != envelope.benchmark_version
        ):
            msg = "12.9 statistical analysis benchmark identity mismatch"
            raise RetrievalError(msg)


def validate_search_evaluation_report(report: object) -> None:
    from productiq.retrieval.evaluation.search_evaluation.reporting.report_schema import (
        SearchEvaluationReport,
    )

    if not isinstance(report, SearchEvaluationReport):
        msg = "report must be SearchEvaluationReport"
        raise RetrievalError(msg)
    forbidden = frozenset({"winner", "best", "recommended", "preferred", "promote", "promotion"})

    def walk_keys(value: object) -> None:
        if isinstance(value, dict):
            for key, nested in value.items():
                if str(key).lower() in forbidden:
                    msg = f"report must not contain evaluative decision field {key!r}"
                    raise RetrievalError(msg)
                walk_keys(nested)
        elif isinstance(value, list):
            for item in value:
                walk_keys(item)

    walk_keys(report.model_dump())


__all__ = ["validate_report_sources", "validate_search_evaluation_report"]
