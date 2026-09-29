"""Search evaluation statistical analysis contracts (Phase 12.9)."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from productiq.retrieval.evaluation.search_evaluation.schema import (
    SEARCH_EVALUATION_CONTRACT_VERSION,
)

SEARCH_STATISTICAL_ANALYSIS_ARTIFACT_SCHEMA_VERSION = "12.9.0"
SEARCH_STATISTICAL_ANALYSIS_FILENAME = "productiq_search_statistical_analysis_v1.json"
SEARCH_STATISTICAL_ANALYSIS_NAME = "productiq_search_statistical_analysis"
SEARCH_STATISTICAL_ANALYSIS_VERSION = "1.0.0"

DEFAULT_BOOTSTRAP_SAMPLES = 5000
DEFAULT_PERMUTATION_SAMPLES = 10000
DEFAULT_STATISTICAL_RANDOM_SEED = 42
DEFAULT_CONFIDENCE_LEVEL = 0.95
SMALL_SAMPLE_QUERY_THRESHOLD = 30


class SearchStatisticalMetricName(StrEnum):
    PRECISION_AT_K = "precision_at_k"
    RECALL_AT_K = "recall_at_k"
    HIT_RATE_AT_K = "hit_rate_at_k"
    NDCG_AT_K = "ndcg_at_k"
    MRR = "mrr"


MultipleTestingMethod = Literal["none", "benjamini_hochberg"]


class BootstrapConfiguration(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    n_bootstrap_samples: int = Field(default=DEFAULT_BOOTSTRAP_SAMPLES, gt=0)
    confidence_level: float = Field(default=DEFAULT_CONFIDENCE_LEVEL, gt=0.0, lt=1.0)
    random_seed: int = Field(default=DEFAULT_STATISTICAL_RANDOM_SEED)
    ci_method: str = Field(
        default="percentile",
        description="Percentile bootstrap on paired mean difference (query-level resampling).",
    )


class PermutationConfiguration(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    n_permutations: int = Field(default=DEFAULT_PERMUTATION_SAMPLES, gt=0)
    random_seed: int = Field(default=DEFAULT_STATISTICAL_RANDOM_SEED)
    test_statistic: str = Field(
        default="abs_mean_paired_difference",
        description="Two-sided test using |mean(d)| under independent sign flips.",
    )


class SearchVariantComparisonPair(BaseModel):
    """Explicit reference vs candidate comparison (no automatic selection)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    reference_variant_name: str = Field(min_length=1)
    candidate_variant_name: str = Field(min_length=1)
    source: Literal["baseline_artifact", "ranking_experiment"] = "baseline_artifact"


class SearchStatisticalAnalysisConfiguration(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    comparison_pairs: tuple[SearchVariantComparisonPair, ...] = Field(min_length=1)
    bootstrap: BootstrapConfiguration = Field(default_factory=BootstrapConfiguration)
    permutation: PermutationConfiguration = Field(default_factory=PermutationConfiguration)
    multiple_testing_method: MultipleTestingMethod = "none"
    small_sample_query_threshold: int = Field(default=SMALL_SAMPLE_QUERY_THRESHOLD, ge=1)


class ConfidenceInterval(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    confidence_level: float = Field(gt=0.0, lt=1.0)
    lower: float
    upper: float
    method: str = Field(min_length=1)


class SearchMetricStatisticalComparison(BaseModel):
    """Paired query-level statistical summary for one metric (and K when applicable)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    reference_variant_name: str = Field(min_length=1)
    candidate_variant_name: str = Field(min_length=1)
    comparison_source: Literal["baseline_artifact", "ranking_experiment"]
    metric_name: SearchStatisticalMetricName
    k: int | None = Field(
        default=None,
        ge=1,
        description="Cutoff K for @K metrics; None for MRR.",
    )
    total_queries: int = Field(ge=0)
    eligible_queries: int = Field(ge=0)
    excluded_queries: int = Field(ge=0)
    exclusion_reasons: tuple[str, ...] = ()
    sample_size: int = Field(ge=0, description="Eligible paired observations used in inference.")
    reference_mean: float | None = None
    candidate_mean: float | None = None
    observed_delta: float | None = Field(
        default=None,
        description="candidate_mean - reference_mean over eligible paired queries.",
    )
    mean_absolute_paired_difference: float | None = None
    bootstrap_configuration: BootstrapConfiguration
    confidence_interval: ConfidenceInterval | None = None
    permutation_configuration: PermutationConfiguration
    p_value: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Monte Carlo two-sided p-value; not a causal claim.",
    )
    multiple_testing_method: MultipleTestingMethod = "none"
    adjusted_p_value: float | None = Field(default=None, ge=0.0, le=1.0)
    small_sample_warning: str | None = None
    limitations: tuple[str, ...] = (
        "Statistical summaries are conditional on the curated benchmark queries only.",
        "Results are descriptive/evidentiary and do not select a winner or promotion.",
    )

    @model_validator(mode="after")
    def validate_counts(self) -> SearchMetricStatisticalComparison:
        if self.total_queries != self.eligible_queries + self.excluded_queries:
            msg = "total_queries must equal eligible_queries + excluded_queries"
            raise ValueError(msg)
        if self.sample_size != self.eligible_queries:
            msg = "sample_size must match eligible_queries"
            raise ValueError(msg)
        if self.metric_name == SearchStatisticalMetricName.MRR:
            if self.k is not None:
                msg = "MRR comparisons must not set k"
                raise ValueError(msg)
            return self
        if self.k is None:
            msg = f"{self.metric_name.value} requires k"
            raise ValueError(msg)
        return self


class SearchStatisticalAnalysisLineage(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    evaluation_version: str = SEARCH_EVALUATION_CONTRACT_VERSION
    analysis_version: str = SEARCH_STATISTICAL_ANALYSIS_VERSION
    benchmark_name: str = Field(min_length=1)
    benchmark_version: str = Field(min_length=1)
    source_baseline_artifacts: tuple[str, ...] = ()
    source_ranking_experiment_artifact: str | None = None


class SearchStatisticalAnalysisResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    analysis_name: str = SEARCH_STATISTICAL_ANALYSIS_NAME
    analysis_version: str = SEARCH_STATISTICAL_ANALYSIS_VERSION
    description: str = Field(default="", min_length=0)
    configuration: SearchStatisticalAnalysisConfiguration
    lineage: SearchStatisticalAnalysisLineage
    comparisons: tuple[SearchMetricStatisticalComparison, ...]
    provenance_notes: tuple[str, ...] = (
        "Paired analysis uses query-aligned Phase 12.3 per-query metrics only.",
        "No retrieval, ranking, or metric recomputation is performed.",
        "No winner, best variant, recommended, or promotion fields are produced.",
    )


def search_statistical_analysis_result_to_dict(
    result: SearchStatisticalAnalysisResult,
) -> dict[str, Any]:
    return result.model_dump(mode="json")


__all__ = [
    "DEFAULT_BOOTSTRAP_SAMPLES",
    "DEFAULT_CONFIDENCE_LEVEL",
    "DEFAULT_PERMUTATION_SAMPLES",
    "DEFAULT_STATISTICAL_RANDOM_SEED",
    "SEARCH_STATISTICAL_ANALYSIS_ARTIFACT_SCHEMA_VERSION",
    "SEARCH_STATISTICAL_ANALYSIS_FILENAME",
    "SEARCH_STATISTICAL_ANALYSIS_NAME",
    "SEARCH_STATISTICAL_ANALYSIS_VERSION",
    "SMALL_SAMPLE_QUERY_THRESHOLD",
    "BootstrapConfiguration",
    "ConfidenceInterval",
    "MultipleTestingMethod",
    "PermutationConfiguration",
    "SearchMetricStatisticalComparison",
    "SearchStatisticalAnalysisConfiguration",
    "SearchStatisticalAnalysisLineage",
    "SearchStatisticalAnalysisResult",
    "SearchStatisticalMetricName",
    "SearchVariantComparisonPair",
    "search_statistical_analysis_result_to_dict",
]
