"""Recommendation pipeline failure observations (Phase 11.9).

Builds on Phase 11.7 evaluation diagnostics without duplicating the offline evaluator.
"""

from __future__ import annotations

from enum import StrEnum

from productiq.recommendation.contracts import (
    RecommendationCandidateGenerationResult,
    RecommendationRequest,
)
from productiq.recommendation.evaluation.diagnostics import RecommendationFailureObservation
from productiq.recommendation.recommendation_pipeline_config import (
    RecommendationPipelineExecutionMetadata,
)


class RecommendationPipelineObservation(StrEnum):
    """Runtime diagnostic observations (not proven root causes)."""

    NO_CANDIDATES = "NO_CANDIDATES"
    PARTIAL_CANDIDATE_GENERATION = "PARTIAL_CANDIDATE_GENERATION"
    SHORTFALL = "SHORTFALL"
    ALL_OUTPUT_REJECTED_BY_SELECTION = "ALL_OUTPUT_REJECTED_BY_SELECTION"


def observe_pipeline_execution(
    *,
    request: RecommendationRequest,
    execution: RecommendationPipelineExecutionMetadata,
    generation: RecommendationCandidateGenerationResult | None = None,
) -> tuple[RecommendationPipelineObservation, ...]:
    """Derive observational categories from pipeline evidence."""
    observations: list[RecommendationPipelineObservation] = []
    if execution.candidate_count == 0:
        observations.append(RecommendationPipelineObservation.NO_CANDIDATES)
    if generation is not None and generation.generator_failures:
        observations.append(RecommendationPipelineObservation.PARTIAL_CANDIDATE_GENERATION)
    if execution.selected_count < request.top_k:
        observations.append(RecommendationPipelineObservation.SHORTFALL)
    if execution.candidate_count > 0 and execution.selected_count == 0:
        observations.append(RecommendationPipelineObservation.ALL_OUTPUT_REJECTED_BY_SELECTION)
    return tuple(dict.fromkeys(observations))


EVALUATION_OBSERVATION_ALIASES: dict[RecommendationFailureObservation, str] = {
    RecommendationFailureObservation.NO_RELEVANT_RETRIEVED: "No judged-relevant item in evaluated top-K",
    RecommendationFailureObservation.RELEVANT_IN_CANDIDATE_POOL_BUT_NOT_TOP_K: (
        "Relevant item in candidate pool but not in ranked top-K"
    ),
    RecommendationFailureObservation.RELEVANT_SELECTED_BEFORE_CONSTRAINTS: (
        "Relevant item ranked highly but absent after selection"
    ),
    RecommendationFailureObservation.RELEVANT_DROPPED_BY_CONSTRAINT: (
        "Relevant item dropped by selection constraints"
    ),
    RecommendationFailureObservation.INSUFFICIENT_CANDIDATES: (
        "Judged relevant item absent from candidate pool"
    ),
    RecommendationFailureObservation.SHORTFALL: "Returned fewer recommendations than requested top_k",
}


__all__ = [
    "EVALUATION_OBSERVATION_ALIASES",
    "RecommendationFailureObservation",
    "RecommendationPipelineObservation",
    "observe_pipeline_execution",
]
