"""Recommendation evaluation result contracts (Phase 11.7)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from productiq.recommendation.evaluation.benchmark_schema import RECOMMENDATION_EVALUATION_VERSION
from productiq.recommendation.evaluation.diagnostics import RecommendationFailureObservation
from productiq.retrieval.evaluation.schema import DEFAULT_EVALUATION_K_VALUES


class RecommendationEvaluationConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    evaluation_version: str = Field(default=RECOMMENDATION_EVALUATION_VERSION, min_length=1)
    evaluation_top_k: int = Field(default=10, gt=0)
    k_values: tuple[int, ...] = DEFAULT_EVALUATION_K_VALUES
    min_relevant_grade: int = Field(
        default=2,
        ge=1,
        le=3,
        description="Judgments at or above this grade count as relevant for P/R/HitRate/MRR.",
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


class RecommendationSeedMetrics(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    seed_product_id: str = Field(min_length=1)
    requested_top_k: int = Field(ge=0)
    returned_count: int = Field(ge=0)
    shortfall_count: int = Field(ge=0)
    shortfall_rate: float = Field(ge=0.0)
    precision_at_k: dict[int, float]
    recall_at_k: dict[int, float | None]
    hit_rate_at_k: dict[int, float]
    ndcg_at_k: dict[int, float | None]
    reciprocal_rank: float
    unique_brand_ratio: float | None = None
    unique_product_type_ratio: float | None = None
    seed_leakage: bool
    duplicate_recommendation_count: int = Field(ge=0)
    max_per_brand_violations: int = Field(ge=0)
    max_per_product_type_violations: int = Field(ge=0)
    candidate_pool_coverage: float | None = Field(default=None, ge=0.0, le=1.0)
    failure_observations: tuple[RecommendationFailureObservation, ...] = ()


class RecommendationAggregateMetrics(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    seed_count: int = Field(ge=1)
    mean_precision_at_k: dict[int, float]
    mean_recall_at_k: dict[int, float]
    recall_aggregate_seed_count: int = Field(ge=0)
    mean_hit_rate_at_k: dict[int, float]
    mean_ndcg_at_k: dict[int, float]
    ndcg_aggregate_seed_count: int = Field(ge=0)
    mrr: float
    mean_shortfall_rate: float = Field(ge=0.0)
    seed_leakage_rate: float = Field(ge=0.0)
    duplicate_recommendation_rate: float = Field(ge=0.0)
    recommendation_catalog_coverage: float | None = None
    k_values: tuple[int, ...]


class RecommendationEvaluationLineage(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    evaluation_version: str = RECOMMENDATION_EVALUATION_VERSION
    benchmark_name: str = Field(min_length=1)
    benchmark_version: str = Field(min_length=1)
    variant_name: str = Field(min_length=1)
    ranker_version: str | None = Field(default=None, min_length=1)
    selection_version: str | None = Field(default=None, min_length=1)
    evaluation_top_k: int = Field(gt=0)
    k_values: tuple[int, ...]
    min_relevant_grade: int = Field(ge=1, le=3)
    catalog_artifact: str | None = None
    source_representation_checksum: str | None = None
    limitations: tuple[str, ...] = (
        "Judgments are curated offline labels, not user-behavior ground truth.",
        "Recall is relative to the judged set only.",
    )


class RecommendationVariantEvaluationResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    lineage: RecommendationEvaluationLineage
    per_seed: tuple[RecommendationSeedMetrics, ...]
    aggregate: RecommendationAggregateMetrics


class RecommendationEvaluationComparison(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    evaluation_version: str = RECOMMENDATION_EVALUATION_VERSION
    baseline_variant: str = Field(min_length=1)
    comparison_variant: str = Field(min_length=1)
    precision_at_k_delta: dict[int, float]
    recall_at_k_delta: dict[int, float]
    hit_rate_at_k_delta: dict[int, float]
    mrr_delta: float
    mean_shortfall_rate_delta: float
    limitations: tuple[str, ...] = (
        "Comparison reports metric deltas only; it does not select a winner.",
    )


class RecommendationBenchmarkEvaluationResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    evaluation_version: str = RECOMMENDATION_EVALUATION_VERSION
    benchmark_name: str = Field(min_length=1)
    benchmark_version: str = Field(min_length=1)
    seed_count: int = Field(ge=1)
    config: RecommendationEvaluationConfig
    baseline: RecommendationVariantEvaluationResult
    with_selection: RecommendationVariantEvaluationResult
    comparison: RecommendationEvaluationComparison


def evaluation_result_to_dict(result: RecommendationBenchmarkEvaluationResult) -> dict[str, Any]:
    return result.model_dump(mode="json")


__all__ = [
    "RecommendationAggregateMetrics",
    "RecommendationBenchmarkEvaluationResult",
    "RecommendationEvaluationComparison",
    "RecommendationEvaluationConfig",
    "RecommendationEvaluationLineage",
    "RecommendationSeedMetrics",
    "RecommendationVariantEvaluationResult",
    "evaluation_result_to_dict",
]
