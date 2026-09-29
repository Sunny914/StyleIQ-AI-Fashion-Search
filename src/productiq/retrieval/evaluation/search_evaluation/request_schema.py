"""Search evaluation request, variant, and metric configuration (Phase 12.1)."""

from __future__ import annotations

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from productiq.retrieval.evaluation.schema import (
    DEFAULT_EVALUATION_K_VALUES,
    DEFAULT_RETRIEVAL_EVALUATION_TOP_K,
)
from productiq.retrieval.evaluation.search_evaluation.benchmark_schema import (
    SearchEvaluationBenchmark,
)
from productiq.retrieval.evaluation.search_evaluation.schema import (
    MAX_SEARCH_RELEVANCE_GRADE,
    SEARCH_EVALUATION_CONTRACT_VERSION,
)


class SearchMetricConfiguration(BaseModel):
    """Metric settings for search evaluation (calculations live in shared metric modules)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    k_values: tuple[int, ...] = DEFAULT_EVALUATION_K_VALUES
    evaluation_top_k: int = Field(default=10, gt=0)
    execution_top_k: int = Field(
        default=DEFAULT_RETRIEVAL_EVALUATION_TOP_K,
        gt=0,
        description=(
            "Maximum ranked products requested from the search variant executor "
            "(distinct from evaluation_top_k used by the metric layer)."
        ),
    )
    min_relevant_grade: int = Field(
        default=2,
        ge=1,
        le=MAX_SEARCH_RELEVANCE_GRADE,
        description="Judgments at or above this grade count as relevant for P/R/HitRate/MRR.",
    )
    compute_ndcg: bool = Field(
        default=True,
        description="When True, nDCG@K uses graded judgment gains (Phase 12.2+ runner).",
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


class SearchEvaluationVariant(BaseModel):
    """Identity for one evaluated search system configuration (implementation-agnostic)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    variant_name: str = Field(min_length=1)
    variant_version: str = Field(min_length=1)
    description: str = Field(default="", min_length=0)
    lineage_labels: tuple[str, ...] = Field(
        default=(),
        description="Opaque lineage tags (e.g. retrieval mode labels); not used by metric math.",
    )

    @field_validator("variant_name", "variant_version")
    @classmethod
    def strip_required(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            msg = "variant identity fields must not be empty"
            raise ValueError(msg)
        return stripped


class SearchRankedResultsForQuery(BaseModel):
    """Ranked product IDs produced by a search variant for one benchmark query."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    query_id: str = Field(min_length=1)
    ranked_product_ids: tuple[str, ...] = ()

    @field_validator("query_id")
    @classmethod
    def strip_query_id(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            msg = "query_id must not be empty"
            raise ValueError(msg)
        return stripped

    @model_validator(mode="after")
    def validate_ranked_product_ids(self) -> Self:
        seen: set[str] = set()
        for raw in self.ranked_product_ids:
            product_id = raw.strip()
            if not product_id:
                msg = "ranked product_id must not be empty"
                raise ValueError(msg)
            if product_id in seen:
                msg = f"duplicate ranked product_id {product_id!r}"
                raise ValueError(msg)
            seen.add(product_id)
        return self


class SearchEvaluationRequest(BaseModel):
    """Inputs for a search evaluation run (runner implemented in Phase 12.2+)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    evaluation_version: str = Field(default=SEARCH_EVALUATION_CONTRACT_VERSION, min_length=1)
    benchmark: SearchEvaluationBenchmark
    variant: SearchEvaluationVariant
    metric_configuration: SearchMetricConfiguration = Field(
        default_factory=SearchMetricConfiguration
    )


__all__ = [
    "SearchEvaluationRequest",
    "SearchEvaluationVariant",
    "SearchMetricConfiguration",
    "SearchRankedResultsForQuery",
]
