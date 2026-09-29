"""Search evaluation result contracts (Phase 12.1)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from productiq.retrieval.evaluation.search_evaluation.request_schema import (
    SearchMetricConfiguration,
)
from productiq.retrieval.evaluation.search_evaluation.schema import (
    SEARCH_EVALUATION_CONTRACT_VERSION,
)


class SearchQueryMetricResult(BaseModel):
    """Per-query search evaluation metrics (query-level, not pooled)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    query_id: str = Field(min_length=1)
    query_text: str = Field(min_length=1)
    query_category: str = Field(min_length=1)
    judged_relevant_count: int = Field(ge=0)
    ranked_product_ids: tuple[str, ...]
    precision_at_k: dict[int, float]
    recall_at_k: dict[int, float | None]
    hit_rate_at_k: dict[int, float]
    ndcg_at_k: dict[int, float | None]
    reciprocal_rank: float
    recall_aggregate_eligible: bool = Field(
        description="False when no judged-relevant products at min_relevant_grade.",
    )


class SearchAggregateMetricResult(BaseModel):
    """Macro-averaged metrics across benchmark queries."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    query_count: int = Field(ge=1)
    recall_aggregate_query_count: int = Field(ge=0)
    ndcg_aggregate_query_count: int = Field(ge=0)
    k_values: tuple[int, ...]
    mean_precision_at_k: dict[int, float]
    mean_recall_at_k: dict[int, float]
    mean_hit_rate_at_k: dict[int, float]
    mean_ndcg_at_k: dict[int, float]
    mrr: float


class SearchEvaluationLineage(BaseModel):
    """Reproducibility metadata (no timestamps in deterministic identity)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    evaluation_version: str = SEARCH_EVALUATION_CONTRACT_VERSION
    benchmark_name: str = Field(min_length=1)
    benchmark_version: str = Field(min_length=1)
    variant_name: str = Field(min_length=1)
    variant_version: str = Field(min_length=1)
    metric_configuration: SearchMetricConfiguration
    catalog_artifact: str | None = None
    source_representation_checksum: str | None = None
    variant_lineage_labels: tuple[str, ...] = ()
    limitations: tuple[str, ...] = (
        "Judgments are curated offline labels, not user-behavior ground truth.",
        "Recall is relative to the judged set only.",
    )


class SearchVariantEvaluationResult(BaseModel):
    """Complete evaluation output for one search variant on one benchmark."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    evaluation_version: str = SEARCH_EVALUATION_CONTRACT_VERSION
    lineage: SearchEvaluationLineage
    per_query: tuple[SearchQueryMetricResult, ...]
    aggregate: SearchAggregateMetricResult


class SearchExperimentComparison(BaseModel):
    """Metric deltas between two variant results (no winner selection)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    evaluation_version: str = SEARCH_EVALUATION_CONTRACT_VERSION
    benchmark_name: str = Field(min_length=1)
    benchmark_version: str = Field(min_length=1)
    baseline_variant: str = Field(min_length=1)
    comparison_variant: str = Field(min_length=1)
    precision_at_k_delta: dict[int, float]
    recall_at_k_delta: dict[int, float]
    hit_rate_at_k_delta: dict[int, float]
    ndcg_at_k_delta: dict[int, float]
    mrr_delta: float
    limitations: tuple[str, ...] = (
        "Comparison reports metric deltas only; it does not select a winner or recommended variant.",
    )


def search_variant_evaluation_result_to_dict(
    result: SearchVariantEvaluationResult,
) -> dict[str, Any]:
    return result.model_dump(mode="json")


def search_experiment_comparison_to_dict(comparison: SearchExperimentComparison) -> dict[str, Any]:
    return comparison.model_dump(mode="json")


__all__ = [
    "SearchAggregateMetricResult",
    "SearchEvaluationLineage",
    "SearchExperimentComparison",
    "SearchQueryMetricResult",
    "SearchVariantEvaluationResult",
    "search_experiment_comparison_to_dict",
    "search_variant_evaluation_result_to_dict",
]
