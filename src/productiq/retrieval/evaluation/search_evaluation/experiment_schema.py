"""Search evaluation experiment contracts (Phase 12.6)."""

from __future__ import annotations

from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from productiq.retrieval.evaluation.search_evaluation.request_schema import (
    SearchMetricConfiguration,
)
from productiq.retrieval.evaluation.search_evaluation.result_schema import (
    SearchExperimentComparison,
)
from productiq.retrieval.evaluation.search_evaluation.schema import (
    SEARCH_EVALUATION_CONTRACT_VERSION,
)

SEARCH_EXPERIMENT_ARTIFACT_SCHEMA_VERSION = "12.6.0"
SEARCH_BASELINE_COMPARISON_EXPERIMENT_NAME = "productiq_search_benchmark_v1_baseline_comparison"
SEARCH_BASELINE_COMPARISON_EXPERIMENT_VERSION = "1.0.0"
SEARCH_BASELINE_COMPARISON_EXPERIMENT_FILENAME = (
    "productiq_search_benchmark_v1_baseline_comparison_experiment_v1.json"
)


class SearchBaselineArtifactReference(BaseModel):
    """Pointer to a persisted Phase 12.5 (or compatible) variant evaluation artifact."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    variant_name: str = Field(min_length=1)
    variant_version: str = Field(min_length=1)
    artifact_path: str = Field(min_length=1)
    deterministic_checksum_sha256: str | None = Field(
        default=None,
        description="Expected checksum of artifact body excluding runtime_metadata.",
    )
    retrieval_index_mode: str | None = Field(
        default=None,
        description="Optional BM25/RRF index scope note from retrieval_provenance.index_mode.",
    )


class SearchEvaluationExperimentDefinition(BaseModel):
    """Controlled grouping of variant evaluations under one evaluation envelope."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    experiment_name: str = Field(min_length=1)
    experiment_version: str = Field(min_length=1)
    description: str = Field(default="", min_length=0)
    reference_variant_name: str = Field(
        min_length=1,
        description="Variant used as numerical reference for aggregate metric deltas.",
    )
    variant_artifacts: tuple[SearchBaselineArtifactReference, ...] = Field(min_length=2)

    @model_validator(mode="after")
    def validate_definition(self) -> Self:
        names = [row.variant_name for row in self.variant_artifacts]
        if len(names) != len(set(names)):
            msg = "experiment variant_name values must be unique"
            raise ValueError(msg)
        if self.reference_variant_name not in names:
            msg = "reference_variant_name must match a variant_artifacts entry"
            raise ValueError(msg)
        return self


class SearchEvaluationExperimentEnvelope(BaseModel):
    """Shared benchmark and metric configuration validated across experiment variants."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    benchmark_name: str = Field(min_length=1)
    benchmark_version: str = Field(min_length=1)
    metric_configuration: SearchMetricConfiguration
    catalog_artifact: str | None = None
    source_representation_checksum: str | None = None


class SearchEvaluationExperimentResult(BaseModel):
    """Descriptive experiment output: envelope + artifact refs + aggregate deltas (no winner)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    experiment_name: str = Field(min_length=1)
    experiment_version: str = Field(min_length=1)
    description: str = Field(default="", min_length=0)
    evaluation_version: str = SEARCH_EVALUATION_CONTRACT_VERSION
    reference_variant_name: str = Field(min_length=1)
    envelope: SearchEvaluationExperimentEnvelope
    variant_artifact_references: tuple[SearchBaselineArtifactReference, ...]
    candidate_comparisons: tuple[SearchExperimentComparison, ...] = Field(
        description="One entry per non-reference variant; deltas are candidate minus reference.",
    )
    provenance_notes: tuple[str, ...] = (
        "Experiment comparisons report absolute metric deltas only.",
        "No winner, best variant, or recommendation is selected.",
    )


def search_evaluation_experiment_result_to_dict(
    result: SearchEvaluationExperimentResult,
) -> dict[str, Any]:
    return result.model_dump(mode="json")


__all__ = [
    "SEARCH_BASELINE_COMPARISON_EXPERIMENT_FILENAME",
    "SEARCH_BASELINE_COMPARISON_EXPERIMENT_NAME",
    "SEARCH_BASELINE_COMPARISON_EXPERIMENT_VERSION",
    "SEARCH_EXPERIMENT_ARTIFACT_SCHEMA_VERSION",
    "SearchBaselineArtifactReference",
    "SearchEvaluationExperimentDefinition",
    "SearchEvaluationExperimentEnvelope",
    "SearchEvaluationExperimentResult",
    "search_evaluation_experiment_result_to_dict",
]
