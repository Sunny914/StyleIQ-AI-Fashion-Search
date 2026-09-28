"""Unified retrieval evaluation contracts (Phase 4.18)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from productiq.retrieval.evaluation.schema import DEFAULT_EVALUATION_K_VALUES

UNIFIED_EVALUATION_FRAMEWORK_VERSION = "1.0.0"
RETRIEVAL_EVALUATION_V1_FILENAME = "retrieval_evaluation_v1.json"
RETRIEVAL_EVALUATION_V1_JSONL_FILENAME = "retrieval_evaluation_v1.jsonl"
RETRIEVAL_COMPARISON_V1_FILENAME = "retrieval_comparison_v1.json"


class EvaluationRequest(BaseModel):
    """Configuration for a unified retrieval evaluation run."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    system_name: str = Field(
        min_length=1,
        description="Logical name for the retrieval system under test (e.g. bm25, semantic, rrf).",
    )
    retrieval_top_k: int = Field(gt=0)
    k_values: tuple[int, ...] = DEFAULT_EVALUATION_K_VALUES
    evaluation_mode: str = Field(
        default="live",
        description="live (Retriever.retrieve) or artifact (pre-recorded lists).",
    )

    @field_validator("k_values")
    @classmethod
    def validate_k_values(cls, value: tuple[int, ...]) -> tuple[int, ...]:
        if not value:
            msg = "k_values must not be empty"
            raise ValueError(msg)
        for k in value:
            if k <= 0:
                msg = "each K must be positive"
                raise ValueError(msg)
        return tuple(sorted(set(value)))


class EvaluationMetrics(BaseModel):
    """Macro-aggregated benchmark metrics (ProductIQ Phase 4.8 conventions)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    mean_precision_at_k: dict[int, float]
    mean_recall_at_k: dict[int, float]
    mrr: float
    query_count: int = Field(ge=1)
    recall_aggregate_query_count: int = Field(ge=0)
    k_values: tuple[int, ...]


class EvaluationQueryResult(BaseModel):
    """Per-query evaluation outcome."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    query_id: str = Field(min_length=1)
    query_text: str = Field(min_length=1)
    category: str = Field(min_length=1)
    judged_relevant_count: int = Field(ge=0)
    retrieved_product_ids: tuple[str, ...]
    retrieval_candidate_count: int = Field(ge=0)
    precision_at_k: dict[int, float]
    recall_at_k: dict[int, float | None]
    reciprocal_rank: float
    recall_aggregate_eligible: bool
    relevant_hits_in_top_k: dict[int, int]
    first_relevant_rank: int | None = None


class CategoryEvaluationResult(BaseModel):
    """Macro metrics for one benchmark query category."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    category: str = Field(min_length=1)
    query_count: int = Field(ge=1)
    judged_relevant_product_count: int = Field(ge=0)
    metrics: EvaluationMetrics


class EvaluationLineage(BaseModel):
    """Provenance for reproducibility; omit fields when unknown."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    framework_version: str = UNIFIED_EVALUATION_FRAMEWORK_VERSION
    benchmark_name: str = Field(min_length=1)
    benchmark_version: str = Field(min_length=1)
    system_name: str = Field(min_length=1)
    retrieval_method: str | None = None
    retrieval_top_k: int = Field(gt=0)
    k_values: tuple[int, ...]
    evaluation_mode: str = Field(min_length=1)
    source_artifact_path: str | None = None
    bm25_index_mode: str | None = None
    embedding_model_id: str | None = None
    embedding_model_revision: str | None = None
    embedding_dimension: int | None = Field(default=None, gt=0)
    similarity_metric: str | None = None
    vector_index_name: str | None = None
    rrf_rank_constant: int | None = Field(default=None, gt=0)
    rrf_bm25_index_mode: str | None = None
    evaluation_timestamp_utc: str | None = None
    limitations: tuple[str, ...] = ()
    extra: dict[str, Any] = Field(default_factory=dict)


class EvaluationResult(BaseModel):
    """Complete evaluation output for one retrieval system on one benchmark."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    productiq_version: str = Field(default="0.1.0")
    lineage: EvaluationLineage
    per_query: tuple[EvaluationQueryResult, ...]
    aggregate: EvaluationMetrics
    by_category: tuple[CategoryEvaluationResult, ...]


class MetricDelta(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    absolute_delta: float
    relative_delta: float | None = Field(
        default=None,
        description="None when baseline is zero or comparison is undefined.",
    )


class EvaluationComparisonResult(BaseModel):
    """Comparison of two evaluation runs without ranking or recommendations."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    framework_version: str = UNIFIED_EVALUATION_FRAMEWORK_VERSION
    compatible: bool
    incompatibility_reasons: tuple[str, ...] = ()
    baseline_system_name: str
    comparison_system_name: str
    baseline_lineage: EvaluationLineage
    comparison_lineage: EvaluationLineage
    precision_at_k_deltas: dict[int, MetricDelta]
    recall_at_k_deltas: dict[int, MetricDelta]
    mrr_delta: MetricDelta
    limitations: tuple[str, ...] = ()


class UnifiedEvaluationCatalog(BaseModel):
    """Multiple system evaluations on the same benchmark snapshot."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    framework_version: str = UNIFIED_EVALUATION_FRAMEWORK_VERSION
    benchmark_name: str
    benchmark_version: str
    incomplete_judgment_warning: str
    query_count: int = Field(ge=1)
    judged_relevant_product_count: int = Field(ge=0)
    generated_at_utc: str
    evaluations: tuple[EvaluationResult, ...]
    comparisons: tuple[EvaluationComparisonResult, ...] = ()


__all__ = [
    "RETRIEVAL_COMPARISON_V1_FILENAME",
    "RETRIEVAL_EVALUATION_V1_FILENAME",
    "RETRIEVAL_EVALUATION_V1_JSONL_FILENAME",
    "UNIFIED_EVALUATION_FRAMEWORK_VERSION",
    "CategoryEvaluationResult",
    "EvaluationComparisonResult",
    "EvaluationLineage",
    "EvaluationMetrics",
    "EvaluationQueryResult",
    "EvaluationRequest",
    "EvaluationResult",
    "MetricDelta",
    "UnifiedEvaluationCatalog",
]
