"""Search ranking experiment contracts (Phase 12.7)."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from productiq.retrieval.contracts import RetrievalCandidate
from productiq.retrieval.evaluation.search_evaluation.request_schema import (
    SearchMetricConfiguration,
)
from productiq.retrieval.evaluation.search_evaluation.result_schema import (
    SearchExperimentComparison,
    SearchVariantEvaluationResult,
)
from productiq.retrieval.evaluation.search_evaluation.schema import (
    SEARCH_EVALUATION_CONTRACT_VERSION,
)

SEARCH_RANKING_EXPERIMENT_ARTIFACT_SCHEMA_VERSION = "12.7.0"
SEARCH_RANKING_EXPERIMENT_NAME = "productiq_search_ranking_experiment"
SEARCH_RANKING_EXPERIMENT_VERSION = "1.0.0"
SEARCH_RANKING_EXPERIMENT_FILENAME = "productiq_search_ranking_experiment_v1.json"

SEARCH_RANKING_VARIANT_RETRIEVAL_ORDER = "productiq_search_ranking_retrieval_order"
SEARCH_RANKING_VARIANT_BASELINE_RANKER = "productiq_search_ranking_baseline_ranker"
SEARCH_RANKING_VARIANT_LTR = "productiq_search_ranking_ltr"

SEARCH_RANKING_VARIANT_VERSION = "1.0.0"


class SearchRankingVariantType(StrEnum):
    RETRIEVAL_ORDER = "retrieval_order"
    BASELINE_RANKER = "baseline_ranker"
    LTR = "ltr"


class SearchRetrievalProvenanceRecord(BaseModel):
    """Candidate-generation retrieval identity (distinct ranking variants)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    retrieval_variant_name: str = Field(min_length=1)
    retrieval_variant_version: str = Field(min_length=1)
    description: str = Field(default="", min_length=0)


class SearchCandidatePoolConfiguration(BaseModel):
    """Fixed candidate pool settings shared by all ranking variants."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    candidate_pool_top_k: int = Field(gt=0)
    require_non_empty_candidates: bool = Field(
        default=True,
        description="When true, every benchmark query must have at least one candidate.",
    )


class SearchRankingVariantConfiguration(BaseModel):
    """Identity and type for one ranking variant under test."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    variant_name: str = Field(min_length=1)
    variant_version: str = Field(min_length=1)
    description: str = Field(default="", min_length=0)
    variant_type: SearchRankingVariantType
    configuration: dict[str, Any] = Field(
        default_factory=dict,
        description="Opaque variant settings; rankers use Phase 10 defaults when empty.",
    )


class SearchQueryCandidateSet(BaseModel):
    """Fixed retrieval candidates for one benchmark query."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    query_id: str = Field(min_length=1)
    candidate_product_ids: tuple[str, ...]
    candidates: tuple[RetrievalCandidate, ...] = ()
    candidate_provenance: str = Field(
        default="",
        description="Descriptive note for how this candidate row was produced.",
    )

    @model_validator(mode="after")
    def validate_candidate_set(self) -> Self:
        if self.candidates:
            ids_from_candidates = tuple(row.product_id for row in self.candidates)
            if ids_from_candidates != self.candidate_product_ids:
                msg = (
                    "candidate_product_ids must match candidates order when candidates are present"
                )
                raise ValueError(msg)
        seen: set[str] = set()
        for product_id in self.candidate_product_ids:
            if not product_id.strip():
                msg = "candidate product_id must not be empty"
                raise ValueError(msg)
            if product_id in seen:
                msg = f"duplicate candidate product_id {product_id!r}"
                raise ValueError(msg)
            seen.add(product_id)
        if self.candidates:
            candidate_ids = [row.product_id for row in self.candidates]
            if len(candidate_ids) != len(set(candidate_ids)):
                msg = "candidates must have unique product_id values"
                raise ValueError(msg)
        return self


class SearchRankingCandidatePool(BaseModel):
    """Full fixed candidate pool for a ranking experiment."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    benchmark_name: str = Field(min_length=1)
    benchmark_version: str = Field(min_length=1)
    candidate_pool_configuration: SearchCandidatePoolConfiguration
    retrieval_provenance: SearchRetrievalProvenanceRecord
    query_candidate_sets: tuple[SearchQueryCandidateSet, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_pool(self) -> Self:
        query_ids = [row.query_id for row in self.query_candidate_sets]
        if len(query_ids) != len(set(query_ids)):
            msg = "query_candidate_sets must have unique query_id values"
            raise ValueError(msg)
        if sorted(query_ids) != query_ids:
            msg = "query_candidate_sets must be sorted by query_id for deterministic serialization"
            raise ValueError(msg)
        config = self.candidate_pool_configuration
        for row in self.query_candidate_sets:
            if len(row.candidate_product_ids) > config.candidate_pool_top_k:
                msg = (
                    f"query {row.query_id!r} has {len(row.candidate_product_ids)} candidates "
                    f"exceeding candidate_pool_top_k={config.candidate_pool_top_k}"
                )
                raise ValueError(msg)
            if config.require_non_empty_candidates and not row.candidate_product_ids:
                msg = f"query {row.query_id!r} requires a non-empty candidate set"
                raise ValueError(msg)
        return self


class SearchRankingExperimentDefinition(BaseModel):
    """Controlled ranking comparison under one fixed candidate pool."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    experiment_name: str = Field(min_length=1)
    experiment_version: str = Field(min_length=1)
    description: str = Field(default="", min_length=0)
    reference_ranking_variant_name: str = Field(min_length=1)
    ranking_variants: tuple[SearchRankingVariantConfiguration, ...] = Field(min_length=2)
    candidate_pool_configuration: SearchCandidatePoolConfiguration
    benchmark_name: str = Field(min_length=1)
    benchmark_version: str = Field(min_length=1)
    metric_configuration: SearchMetricConfiguration
    retrieval_provenance: SearchRetrievalProvenanceRecord
    catalog_artifact: str | None = None
    source_representation_checksum: str | None = None

    @model_validator(mode="after")
    def validate_definition(self) -> Self:
        names = [row.variant_name for row in self.ranking_variants]
        if len(names) != len(set(names)):
            msg = "ranking variant_name values must be unique"
            raise ValueError(msg)
        if self.reference_ranking_variant_name not in names:
            msg = "reference_ranking_variant_name must match a ranking_variants entry"
            raise ValueError(msg)
        return self


class SearchRankingExperimentEnvelope(BaseModel):
    """Shared benchmark, metric, candidate, and retrieval settings."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    benchmark_name: str = Field(min_length=1)
    benchmark_version: str = Field(min_length=1)
    metric_configuration: SearchMetricConfiguration
    candidate_pool_configuration: SearchCandidatePoolConfiguration
    retrieval_provenance: SearchRetrievalProvenanceRecord
    catalog_artifact: str | None = None
    source_representation_checksum: str | None = None


class SearchRankingExperimentResult(BaseModel):
    """Descriptive ranking experiment output (no winner selection)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    experiment_name: str = Field(min_length=1)
    experiment_version: str = Field(min_length=1)
    description: str = Field(default="", min_length=0)
    evaluation_version: str = SEARCH_EVALUATION_CONTRACT_VERSION
    reference_ranking_variant_name: str = Field(min_length=1)
    envelope: SearchRankingExperimentEnvelope
    candidate_pool: SearchRankingCandidatePool
    variant_evaluation_results: tuple[SearchVariantEvaluationResult, ...]
    candidate_comparisons: tuple[SearchExperimentComparison, ...] = Field(
        description="One entry per non-reference ranking variant; deltas are candidate minus reference.",
    )
    provenance_notes: tuple[str, ...] = (
        "Ranking experiment comparisons report absolute metric deltas only.",
        "All ranking variants consumed the same fixed candidate set per query.",
        "No winner, best variant, or recommendation is selected.",
    )


def search_ranking_experiment_result_to_dict(
    result: SearchRankingExperimentResult,
) -> dict[str, Any]:
    return result.model_dump(mode="json")


__all__ = [
    "SEARCH_RANKING_EXPERIMENT_ARTIFACT_SCHEMA_VERSION",
    "SEARCH_RANKING_EXPERIMENT_FILENAME",
    "SEARCH_RANKING_EXPERIMENT_NAME",
    "SEARCH_RANKING_EXPERIMENT_VERSION",
    "SEARCH_RANKING_VARIANT_BASELINE_RANKER",
    "SEARCH_RANKING_VARIANT_LTR",
    "SEARCH_RANKING_VARIANT_RETRIEVAL_ORDER",
    "SEARCH_RANKING_VARIANT_VERSION",
    "SearchCandidatePoolConfiguration",
    "SearchQueryCandidateSet",
    "SearchRankingCandidatePool",
    "SearchRankingExperimentDefinition",
    "SearchRankingExperimentEnvelope",
    "SearchRankingExperimentResult",
    "SearchRankingVariantConfiguration",
    "SearchRankingVariantType",
    "SearchRetrievalProvenanceRecord",
    "search_ranking_experiment_result_to_dict",
]
