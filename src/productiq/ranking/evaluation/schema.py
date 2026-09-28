"""Ranking evaluation contracts (Phase 10.6)."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from productiq.retrieval.evaluation.contracts import QueryEvaluationResult
from productiq.retrieval.evaluation.schema import DEFAULT_EVALUATION_K_VALUES
from productiq.retrieval.evaluation.unified_evaluation_schema import EvaluationMetrics

RANKING_EVALUATION_VERSION = "10.6.0"
RRF_RANKING_SYSTEM_NAME = "rrf_retrieval_order"
BASELINE_RANKING_SYSTEM_NAME = "baseline_ranker_10_4"


class RankingDiagnosticTag(StrEnum):
    RELEVANT_NOT_IN_CANDIDATE_POOL = "RELEVANT_NOT_IN_CANDIDATE_POOL"
    RELEVANT_RETRIEVED_BUT_RANKED_LOW = "RELEVANT_RETRIEVED_BUT_RANKED_LOW"
    RELEVANT_RANKED_HIGH = "RELEVANT_RANKED_HIGH"


class RankingEvaluationConfig(BaseModel):
    """Fixed offline ranking evaluation settings (not tuned)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    evaluation_top_k: int = Field(
        default=50,
        gt=0,
        description="Final ordered list depth used for metric computation.",
    )
    k_values: tuple[int, ...] = DEFAULT_EVALUATION_K_VALUES
    candidate_pool_top_k: int = Field(
        default=50,
        gt=0,
        description="Must match ProductionRetrievalConfig.candidate_pool_top_k.",
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


class RankingEvaluationLineage(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    evaluation_version: str = RANKING_EVALUATION_VERSION
    benchmark_name: str = Field(min_length=1)
    benchmark_version: str = Field(min_length=1)
    evaluation_top_k: int = Field(gt=0)
    candidate_pool_top_k: int = Field(gt=0)
    k_values: tuple[int, ...]
    ranking_version: str | None = Field(default=None, min_length=1)
    feature_schema_version: str | None = Field(default=None, min_length=1)
    normalization_schema_version: str | None = Field(default=None, min_length=1)
    ranking_pipeline_version: str | None = Field(default=None, min_length=1)
    limitations: tuple[str, ...] = (
        "Phase 10.6 evaluates the fixed Phase 10.4 baseline configuration; weights are not tuned.",
    )


class RankingQueryDiagnostics(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    diagnostic_tags: tuple[RankingDiagnosticTag, ...] = ()
    relevant_missing_from_pool_product_ids: tuple[str, ...] = ()
    relevant_in_pool_not_in_evaluated_top_product_ids: tuple[str, ...] = ()


class RankingQueryEvaluationResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    query_id: str = Field(min_length=1)
    query_text: str = Field(min_length=1)
    category: str = Field(min_length=1)
    judged_relevant_count: int = Field(ge=0)
    filtered_pool_candidate_count: int = Field(ge=0)
    candidate_coverage: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Share of judged relevant IDs present in the filtered candidate pool.",
    )
    rrf: QueryEvaluationResult
    baseline: QueryEvaluationResult
    diagnostics: RankingQueryDiagnostics


class RankingSystemEvaluationResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    system_name: str = Field(min_length=1)
    lineage: RankingEvaluationLineage
    per_query: tuple[RankingQueryEvaluationResult, ...]
    aggregate: EvaluationMetrics


class MetricComparisonValue(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    rrf: float
    baseline: float
    delta: float = Field(description="baseline minus rrf (positive means baseline higher).")


class RankingEvaluationComparison(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    mrr: MetricComparisonValue
    precision_at_k: dict[int, MetricComparisonValue]
    recall_at_k: dict[int, MetricComparisonValue]
    limitations: tuple[str, ...] = (
        "Comparison reports metric deltas only; it does not select a winner or recommend changes.",
    )


class RankingBenchmarkEvaluationResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    evaluation_version: str = RANKING_EVALUATION_VERSION
    benchmark_name: str = Field(min_length=1)
    benchmark_version: str = Field(min_length=1)
    query_count: int = Field(ge=1)
    total_judged_relevance_count: int = Field(ge=0)
    evaluation_top_k: int = Field(gt=0)
    candidate_pool_top_k: int = Field(gt=0)
    k_values: tuple[int, ...]
    rrf: EvaluationMetrics
    baseline: EvaluationMetrics
    per_query: tuple[RankingQueryEvaluationResult, ...]
    comparison: RankingEvaluationComparison
    lineage: RankingEvaluationLineage


__all__ = [
    "BASELINE_RANKING_SYSTEM_NAME",
    "RANKING_EVALUATION_VERSION",
    "RRF_RANKING_SYSTEM_NAME",
    "MetricComparisonValue",
    "RankingBenchmarkEvaluationResult",
    "RankingDiagnosticTag",
    "RankingEvaluationComparison",
    "RankingEvaluationConfig",
    "RankingEvaluationLineage",
    "RankingQueryDiagnostics",
    "RankingQueryEvaluationResult",
    "RankingSystemEvaluationResult",
]
