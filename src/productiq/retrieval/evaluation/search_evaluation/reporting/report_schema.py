"""Search evaluation reporting contracts (Phase 12.10)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from productiq.retrieval.evaluation.search_evaluation.request_schema import (
    SearchMetricConfiguration,
)
from productiq.retrieval.evaluation.search_evaluation.schema import (
    SEARCH_EVALUATION_CONTRACT_VERSION,
)

SEARCH_EVALUATION_REPORT_ARTIFACT_SCHEMA_VERSION = "12.10.0"
SEARCH_EVALUATION_REPORT_FILENAME = "productiq_search_evaluation_report_v1.json"
SEARCH_EVALUATION_REPORT_MARKDOWN_FILENAME = "productiq_search_evaluation_report_v1.md"
SEARCH_EVALUATION_REPORT_NAME = "productiq_search_evaluation_report"
SEARCH_EVALUATION_REPORT_VERSION = "1.0.0"

ComparisonSourceKind = Literal[
    "baseline_experiment",
    "ranking_experiment",
]


class SearchEvaluationReportMetadata(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    report_name: str = SEARCH_EVALUATION_REPORT_NAME
    report_version: str = SEARCH_EVALUATION_REPORT_VERSION
    evaluation_contract_version: str = SEARCH_EVALUATION_CONTRACT_VERSION
    description: str = Field(default="", min_length=0)


class SearchEvaluationBenchmarkReference(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    benchmark_name: str = Field(min_length=1)
    benchmark_version: str = Field(min_length=1)
    benchmark_artifact_path: str = Field(min_length=1)
    benchmark_artifact_schema_version: str = Field(min_length=1)
    benchmark_checksum_sha256: str | None = None
    query_count: int = Field(ge=1)


class SearchEvaluationReportConfiguration(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    metric_configuration: SearchMetricConfiguration
    execution_top_k: int = Field(gt=0)
    evaluation_top_k: int = Field(gt=0)


class SearchEvaluationMetricSummaryRow(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    metric_name: str = Field(min_length=1)
    k: int | None = Field(default=None, ge=1)
    value: float
    eligible_query_count: int | None = Field(default=None, ge=0)


class SearchEvaluationVariantSummary(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    variant_name: str = Field(min_length=1)
    variant_version: str = Field(min_length=1)
    source_phase: str = Field(min_length=1)
    artifact_path: str = Field(min_length=1)
    artifact_schema_version: str = Field(min_length=1)
    artifact_checksum_sha256: str | None = None
    retrieval_index_mode: str | None = None
    query_count: int = Field(ge=1)
    recall_aggregate_query_count: int = Field(ge=0)
    ndcg_aggregate_query_count: int = Field(ge=0)
    metrics: tuple[SearchEvaluationMetricSummaryRow, ...]


class SearchEvaluationPairwiseComparisonRow(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    comparison_source: ComparisonSourceKind
    reference_variant_name: str = Field(min_length=1)
    candidate_variant_name: str = Field(min_length=1)
    metric_name: str = Field(min_length=1)
    k: int | None = Field(default=None, ge=1)
    reference_value: float
    candidate_value: float
    absolute_delta: float


class SearchEvaluationFailureAggregateSummaryRow(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    variant_name: str = Field(min_length=1)
    analysis_k: int = Field(gt=0)
    failure_category: str = Field(min_length=1)
    record_count: int = Field(ge=0)


class SearchEvaluationRetrievalPatternSummaryRow(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    pattern: str = Field(min_length=1)
    product_count: int = Field(ge=0)


class SearchEvaluationFailureAnalysisSummary(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    analysis_artifact_path: str = Field(min_length=1)
    analysis_artifact_schema_version: str = Field(min_length=1)
    failure_record_count: int = Field(ge=0)
    aggregate_rows: tuple[SearchEvaluationFailureAggregateSummaryRow, ...] = ()
    retrieval_pattern_rows: tuple[SearchEvaluationRetrievalPatternSummaryRow, ...] = ()
    diagnostic_limitations: tuple[str, ...] = ()


class SearchEvaluationStatisticalComparisonSummaryRow(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    reference_variant_name: str = Field(min_length=1)
    candidate_variant_name: str = Field(min_length=1)
    metric_name: str = Field(min_length=1)
    k: int | None = Field(default=None, ge=1)
    total_queries: int = Field(ge=0)
    eligible_queries: int = Field(ge=0)
    excluded_queries: int = Field(ge=0)
    exclusion_reasons: tuple[str, ...] = ()
    reference_mean: float | None = None
    candidate_mean: float | None = None
    observed_delta: float | None = None
    bootstrap_n_samples: int = Field(ge=0)
    bootstrap_confidence_level: float = Field(ge=0.0, le=1.0)
    bootstrap_random_seed: int
    confidence_interval_lower: float | None = None
    confidence_interval_upper: float | None = None
    permutation_n_samples: int = Field(ge=0)
    permutation_random_seed: int
    p_value: float | None = Field(default=None, ge=0.0, le=1.0)
    multiple_testing_method: str = Field(min_length=1)
    adjusted_p_value: float | None = Field(default=None, ge=0.0, le=1.0)
    small_sample_warning: str | None = None


class SearchEvaluationStatisticalAnalysisSummary(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    analysis_artifact_path: str = Field(min_length=1)
    analysis_artifact_schema_version: str = Field(min_length=1)
    comparisons: tuple[SearchEvaluationStatisticalComparisonSummaryRow, ...] = ()


class SearchEvaluationSourceArtifactReference(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    pipeline_stage: str = Field(min_length=1)
    artifact_path: str = Field(min_length=1)
    artifact_schema_version: str = Field(min_length=1)
    deterministic_checksum_sha256: str | None = None


class SearchEvaluationReproducibilityManifest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    benchmark_name: str = Field(min_length=1)
    benchmark_version: str = Field(min_length=1)
    evaluation_contract_version: str = SEARCH_EVALUATION_CONTRACT_VERSION
    metric_configuration: SearchMetricConfiguration
    execution_top_k: int = Field(gt=0)
    evaluation_top_k: int = Field(gt=0)
    catalog_artifact: str | None = None
    source_representation_checksum: str | None = None
    source_artifacts: tuple[SearchEvaluationSourceArtifactReference, ...]
    variant_identities: tuple[tuple[str, str], ...]
    variant_artifact_checksums: tuple[tuple[str, str | None], ...]
    retrieval_index_modes: tuple[tuple[str, str | None], ...]
    ltr_artifact_path: str | None = None
    ltr_artifact_present: bool = False
    statistical_bootstrap_seed: int | None = None
    statistical_permutation_seed: int | None = None
    statistical_multiple_testing_method: str | None = None
    schema_versions: tuple[tuple[str, str], ...]
    reproducibility_limitations: tuple[str, ...] = ()


class SearchEvaluationReport(BaseModel):
    """Canonical Phase 12 evaluation report (read-only synthesis)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    metadata: SearchEvaluationReportMetadata
    benchmark: SearchEvaluationBenchmarkReference
    configuration: SearchEvaluationReportConfiguration
    variant_summaries: tuple[SearchEvaluationVariantSummary, ...]
    pairwise_comparisons: tuple[SearchEvaluationPairwiseComparisonRow, ...]
    failure_analysis: SearchEvaluationFailureAnalysisSummary | None = None
    statistical_analysis: SearchEvaluationStatisticalAnalysisSummary | None = None
    reproducibility: SearchEvaluationReproducibilityManifest
    limitations: tuple[str, ...] = (
        "Report values are copied from persisted Phase 12 artifacts; metrics are not recomputed.",
        "No winner, best variant, recommended, promotion, or deployment decision is selected.",
    )


def search_evaluation_report_to_dict(report: SearchEvaluationReport) -> dict[str, Any]:
    return report.model_dump(mode="json")


__all__ = [
    "SEARCH_EVALUATION_REPORT_ARTIFACT_SCHEMA_VERSION",
    "SEARCH_EVALUATION_REPORT_FILENAME",
    "SEARCH_EVALUATION_REPORT_MARKDOWN_FILENAME",
    "SEARCH_EVALUATION_REPORT_NAME",
    "SEARCH_EVALUATION_REPORT_VERSION",
    "SearchEvaluationBenchmarkReference",
    "SearchEvaluationFailureAggregateSummaryRow",
    "SearchEvaluationFailureAnalysisSummary",
    "SearchEvaluationMetricSummaryRow",
    "SearchEvaluationPairwiseComparisonRow",
    "SearchEvaluationReport",
    "SearchEvaluationReportConfiguration",
    "SearchEvaluationReportMetadata",
    "SearchEvaluationReproducibilityManifest",
    "SearchEvaluationRetrievalPatternSummaryRow",
    "SearchEvaluationSourceArtifactReference",
    "SearchEvaluationStatisticalAnalysisSummary",
    "SearchEvaluationStatisticalComparisonSummaryRow",
    "SearchEvaluationVariantSummary",
    "search_evaluation_report_to_dict",
]
