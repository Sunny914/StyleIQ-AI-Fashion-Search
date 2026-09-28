"""Recommendation pipeline hardening (Phase 11.9)."""

from __future__ import annotations

import importlib
from typing import Any

from productiq.recommendation.hardening.config import (
    RECOMMENDATION_FAILURE_ANALYSIS_VERSION,
    RECOMMENDATION_HARDENING_VERSION,
)

__all__ = [
    "EVALUATION_OBSERVATION_ALIASES",
    "RECOMMENDATION_FAILURE_ANALYSIS_VERSION",
    "RECOMMENDATION_HARDENING_VERSION",
    "RecommendationPipelineObservation",
    "assert_no_experimental_recommendation_rankers",
    "assert_production_recommendation_configuration",
    "assert_production_recommendation_request",
    "assert_production_recommendation_type",
    "observe_pipeline_execution",
    "validate_candidate_generation_invariants",
    "validate_content_similarity_batch",
    "validate_pipeline_configuration",
    "validate_pipeline_guardrail_response",
    "validate_production_pipeline_response",
    "validate_ranked_recommendations_invariants",
    "validate_recommendation_features_batch",
    "validate_selection_output_constraints",
]

_LAZY: dict[str, tuple[str, str]] = {
    "assert_no_experimental_recommendation_rankers": (
        "productiq.recommendation.hardening.production_safety",
        "assert_no_experimental_recommendation_rankers",
    ),
    "assert_production_recommendation_configuration": (
        "productiq.recommendation.hardening.production_safety",
        "assert_production_recommendation_configuration",
    ),
    "assert_production_recommendation_request": (
        "productiq.recommendation.hardening.production_safety",
        "assert_production_recommendation_request",
    ),
    "assert_production_recommendation_type": (
        "productiq.recommendation.hardening.production_safety",
        "assert_production_recommendation_type",
    ),
    "observe_pipeline_execution": (
        "productiq.recommendation.hardening.failure_analysis",
        "observe_pipeline_execution",
    ),
    "EVALUATION_OBSERVATION_ALIASES": (
        "productiq.recommendation.hardening.failure_analysis",
        "EVALUATION_OBSERVATION_ALIASES",
    ),
    "RecommendationPipelineObservation": (
        "productiq.recommendation.hardening.failure_analysis",
        "RecommendationPipelineObservation",
    ),
    "validate_candidate_generation_invariants": (
        "productiq.recommendation.hardening.pipeline_invariants",
        "validate_candidate_generation_invariants",
    ),
    "validate_content_similarity_batch": (
        "productiq.recommendation.hardening.pipeline_invariants",
        "validate_content_similarity_batch",
    ),
    "validate_pipeline_configuration": (
        "productiq.recommendation.hardening.pipeline_invariants",
        "validate_pipeline_configuration",
    ),
    "validate_pipeline_guardrail_response": (
        "productiq.recommendation.hardening.pipeline_invariants",
        "validate_pipeline_guardrail_response",
    ),
    "validate_production_pipeline_response": (
        "productiq.recommendation.hardening.pipeline_invariants",
        "validate_production_pipeline_response",
    ),
    "validate_ranked_recommendations_invariants": (
        "productiq.recommendation.hardening.pipeline_invariants",
        "validate_ranked_recommendations_invariants",
    ),
    "validate_recommendation_features_batch": (
        "productiq.recommendation.hardening.pipeline_invariants",
        "validate_recommendation_features_batch",
    ),
    "validate_selection_output_constraints": (
        "productiq.recommendation.hardening.pipeline_invariants",
        "validate_selection_output_constraints",
    ),
}


def __getattr__(name: str) -> Any:
    if name not in _LAZY:
        msg = f"module {__name__!r} has no attribute {name!r}"
        raise AttributeError(msg)
    module_path, attr = _LAZY[name]
    module = importlib.import_module(module_path)
    return getattr(module, attr)
