"""Evaluation result contracts (Phase 4.8)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from productiq.retrieval.evaluation.schema import DEFAULT_EVALUATION_K_VALUES


class PerQueryMetricValues(BaseModel):
    """Metric values for one query at configured K values."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    precision_at_k: dict[int, float]
    recall_at_k: dict[int, float | None]
    reciprocal_rank: float
    recall_aggregate_eligible: bool = Field(
        description="False when ground-truth relevance set is empty; recall is excluded from macro recall."
    )
    retrieved_product_ids: tuple[str, ...]
    relevant_hits_in_top_k: dict[int, int]
    first_relevant_rank: int | None = Field(
        default=None,
        description="1-based rank of first relevant product in retrieved list; None if none in list.",
    )


class QueryEvaluationResult(BaseModel):
    """Evaluation outcome for one benchmark query."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    query_id: str = Field(min_length=1)
    query_text: str = Field(min_length=1)
    category: str = Field(min_length=1)
    judged_relevant_count: int = Field(ge=0)
    metrics: PerQueryMetricValues
    retrieval_candidate_count: int = Field(ge=0)


class AggregateMetricValues(BaseModel):
    """Macro-aggregated metrics across evaluation queries."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    mean_precision_at_k: dict[int, float]
    mean_recall_at_k: dict[int, float]
    mrr: float
    query_count: int = Field(ge=1)
    recall_aggregate_query_count: int = Field(
        ge=0,
        description="Queries included in mean recall (non-empty ground truth).",
    )
    k_values: tuple[int, ...]

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
        return value


class LexicalRetrievalEvaluationResult(BaseModel):
    """Full evaluation run output."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    benchmark_name: str = Field(min_length=1)
    benchmark_version: str = Field(min_length=1)
    retrieval_top_k: int = Field(gt=0)
    k_values: tuple[int, ...] = DEFAULT_EVALUATION_K_VALUES
    per_query: tuple[QueryEvaluationResult, ...]
    aggregate: AggregateMetricValues


__all__ = [
    "AggregateMetricValues",
    "LexicalRetrievalEvaluationResult",
    "PerQueryMetricValues",
    "QueryEvaluationResult",
]
