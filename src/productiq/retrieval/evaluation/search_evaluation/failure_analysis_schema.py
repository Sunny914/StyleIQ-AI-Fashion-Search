"""Search evaluation failure-analysis contracts (Phase 12.8)."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from productiq.retrieval.evaluation.search_evaluation.schema import (
    SEARCH_EVALUATION_CONTRACT_VERSION,
)

SEARCH_FAILURE_ANALYSIS_ARTIFACT_SCHEMA_VERSION = "12.8.0"
SEARCH_FAILURE_ANALYSIS_FILENAME = "productiq_search_failure_analysis_v1.json"
SEARCH_FAILURE_ANALYSIS_NAME = "productiq_search_failure_analysis"
SEARCH_FAILURE_ANALYSIS_VERSION = "1.0.0"


class SearchFailureCategory(StrEnum):
    """Observed evaluation outcome for one judged product (not causal root cause)."""

    RANKED_IN_TOP_K = "RANKED_IN_TOP_K"
    RETRIEVED_BELOW_K = "RETRIEVED_BELOW_K"
    DEPTH_LIMITED = "DEPTH_LIMITED"
    ABSENT_FROM_EVALUATED_DEPTH = "ABSENT_FROM_EVALUATED_DEPTH"
    NOT_RETRIEVED = "NOT_RETRIEVED"
    JUDGED_RELEVANT_BUT_CONSTRAINT_INCOMPATIBLE = "JUDGED_RELEVANT_BUT_CONSTRAINT_INCOMPATIBLE"


class SearchFailureAnalysisRecord(BaseModel):
    """One diagnostic row for a judged product under one analyzed variant and K."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    query_id: str = Field(min_length=1)
    product_id: str = Field(min_length=1)
    relevance_grade: int = Field(ge=0)
    variant_name: str = Field(min_length=1)
    variant_version: str = Field(min_length=1)
    analysis_k: int = Field(gt=0)
    evaluated_depth: int = Field(gt=0, description="Depth available in source artifact ranked list.")
    retrieved: bool
    in_top_k: bool
    retrieval_rank: int | None = Field(
        default=None,
        ge=1,
        description="1-based rank in artifact list; None when absent from evaluated depth.",
    )
    ranking_rank: int | None = Field(
        default=None,
        ge=1,
        description="Same as retrieval_rank for ranking experiments when applicable.",
    )
    reference_rank: int | None = Field(default=None, ge=1)
    rank_delta: int | None = Field(
        default=None,
        description="candidate_rank - reference_rank when both ranks are known.",
    )
    failure_category: SearchFailureCategory
    observations: tuple[str, ...] = ()


class SearchFailureAnalysisConfiguration(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    analysis_k_values: tuple[int, ...] = (1, 5, 10, 20, 50)
    min_relevant_grade: int = Field(default=2, ge=1)
    depth_limited_threshold: int = Field(
        default=10,
        gt=0,
        description="Known rank must exceed this value to qualify for DEPTH_LIMITED.",
    )
    enable_constraint_diagnostics: bool = False


class SearchFailureAggregateRow(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    variant_name: str = Field(min_length=1)
    analysis_k: int = Field(gt=0)
    failure_category: SearchFailureCategory
    record_count: int = Field(ge=0)
    relevance_grade: int | None = Field(default=None, ge=0)
    query_id: str | None = None


class SearchRetrievalRelationshipAggregate(BaseModel):
    """Cross-method retrieval pattern counts (Phase 4.18 compatible labels)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    pattern: str = Field(min_length=1)
    product_count: int = Field(ge=0)


class SearchFailureAnalysisLineage(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    evaluation_version: str = SEARCH_EVALUATION_CONTRACT_VERSION
    analysis_version: str = SEARCH_FAILURE_ANALYSIS_VERSION
    benchmark_name: str = Field(min_length=1)
    benchmark_version: str = Field(min_length=1)
    source_baseline_artifacts: tuple[str, ...] = ()
    source_ranking_experiment_artifact: str | None = None


class SearchFailureAnalysisResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    analysis_name: str = SEARCH_FAILURE_ANALYSIS_NAME
    analysis_version: str = SEARCH_FAILURE_ANALYSIS_VERSION
    description: str = Field(default="", min_length=0)
    configuration: SearchFailureAnalysisConfiguration
    lineage: SearchFailureAnalysisLineage
    failure_taxonomy: tuple[str, ...]
    records: tuple[SearchFailureAnalysisRecord, ...]
    aggregates: tuple[SearchFailureAggregateRow, ...]
    retrieval_relationship_aggregates: tuple[SearchRetrievalRelationshipAggregate, ...] = ()
    provenance_notes: tuple[str, ...] = (
        "Diagnostics describe observed artifact outcomes only.",
        "Categories are not causal root-cause verdicts.",
    )

    @model_validator(mode="after")
    def validate_unique_record_keys(self) -> SearchFailureAnalysisResult:
        seen: set[tuple[str, str, str, int]] = set()
        for row in self.records:
            key = (row.query_id, row.product_id, row.variant_name, row.analysis_k)
            if key in seen:
                msg = f"duplicate failure analysis record for {key!r}"
                raise ValueError(msg)
            seen.add(key)
        return self


def search_failure_analysis_result_to_dict(result: SearchFailureAnalysisResult) -> dict[str, Any]:
    return result.model_dump(mode="json")


__all__ = [
    "SEARCH_FAILURE_ANALYSIS_ARTIFACT_SCHEMA_VERSION",
    "SEARCH_FAILURE_ANALYSIS_FILENAME",
    "SEARCH_FAILURE_ANALYSIS_NAME",
    "SEARCH_FAILURE_ANALYSIS_VERSION",
    "SearchFailureAggregateRow",
    "SearchFailureAnalysisConfiguration",
    "SearchFailureAnalysisLineage",
    "SearchFailureAnalysisRecord",
    "SearchFailureAnalysisResult",
    "SearchFailureCategory",
    "SearchRetrievalRelationshipAggregate",
    "search_failure_analysis_result_to_dict",
]
