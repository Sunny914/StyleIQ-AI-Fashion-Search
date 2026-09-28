"""Baseline vs LTR offline comparison contracts (Phase 10.8)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from productiq.ranking.evaluation.schema import RankingQueryDiagnostics
from productiq.ranking.ltr.inference_config import LTR_BASELINE_COMPARISON_VERSION
from productiq.retrieval.evaluation.contracts import QueryEvaluationResult
from productiq.retrieval.evaluation.unified_evaluation_schema import EvaluationMetrics

BASELINE_LTR_SYSTEM_BASELINE = "baseline_ranker_10_4"
BASELINE_LTR_SYSTEM_LTR = "ltr_inference_10_8"


class BaselineLTRMetricComparisonValue(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    baseline: float
    ltr: float
    delta: float = Field(description="ltr minus baseline (positive means LTR higher).")


class BaselineLTRRankingComparison(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    mrr: BaselineLTRMetricComparisonValue
    precision_at_k: dict[int, BaselineLTRMetricComparisonValue]
    recall_at_k: dict[int, BaselineLTRMetricComparisonValue]
    limitations: tuple[str, ...] = (
        "Comparison reports metric deltas only; it does not select a winner or recommend changes.",
    )


class LTRBaselineEvaluationLineage(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    evaluation_version: str = LTR_BASELINE_COMPARISON_VERSION
    benchmark_name: str = Field(min_length=1)
    benchmark_version: str = Field(min_length=1)
    evaluation_top_k: int = Field(gt=0)
    candidate_pool_top_k: int = Field(gt=0)
    k_values: tuple[int, ...]
    baseline_ranking_version: str = Field(min_length=1)
    ltr_inference_version: str = Field(min_length=1)
    ltr_artifact_version: str = Field(min_length=1)
    ltr_model_version: str = Field(min_length=1)
    feature_schema_version: str = Field(min_length=1)
    normalization_schema_version: str = Field(min_length=1)
    ltr_feature_order_version: str = Field(min_length=1)
    missing_value_policy_version: str = Field(min_length=1)
    query_set_version: str | None = None
    judgment_source_version: str | None = None
    limitations: tuple[str, ...] = (
        "Phase 10.8 compares fixed Phase 10.4 baseline vs offline LTR on the same filtered pool.",
        "LTR is not the production ranking path.",
    )


class LTRBaselineQueryEvaluationResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    query_id: str = Field(min_length=1)
    query_text: str = Field(min_length=1)
    category: str = Field(min_length=1)
    judged_relevant_count: int = Field(ge=0)
    filtered_pool_candidate_count: int = Field(ge=0)
    candidate_coverage: float | None = Field(default=None, ge=0.0, le=1.0)
    baseline: QueryEvaluationResult
    ltr: QueryEvaluationResult
    diagnostics: RankingQueryDiagnostics


class LTRBaselineBenchmarkEvaluationResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    evaluation_version: str = LTR_BASELINE_COMPARISON_VERSION
    benchmark_name: str = Field(min_length=1)
    benchmark_version: str = Field(min_length=1)
    query_count: int = Field(ge=1)
    total_judged_relevance_count: int = Field(ge=0)
    evaluation_top_k: int = Field(gt=0)
    candidate_pool_top_k: int = Field(gt=0)
    k_values: tuple[int, ...]
    baseline: EvaluationMetrics
    ltr: EvaluationMetrics
    per_query: tuple[LTRBaselineQueryEvaluationResult, ...]
    comparison: BaselineLTRRankingComparison
    lineage: LTRBaselineEvaluationLineage


__all__ = [
    "BASELINE_LTR_SYSTEM_BASELINE",
    "BASELINE_LTR_SYSTEM_LTR",
    "BaselineLTRMetricComparisonValue",
    "BaselineLTRRankingComparison",
    "LTRBaselineBenchmarkEvaluationResult",
    "LTRBaselineEvaluationLineage",
    "LTRBaselineQueryEvaluationResult",
]
