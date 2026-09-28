"""Production recommendation safety guardrails (Phase 11.9)."""

from __future__ import annotations

from productiq.exceptions.base import RecommendationError
from productiq.recommendation.config import RecommendationConfig
from productiq.recommendation.contracts import (
    IMPLEMENTED_RECOMMENDATION_TYPES,
    RecommendationRequest,
    RecommendationType,
)


def assert_production_recommendation_type(recommendation_type: RecommendationType) -> None:
    """Production path supports only implemented recommendation modes."""
    if recommendation_type not in IMPLEMENTED_RECOMMENDATION_TYPES:
        msg = f"production recommendation supports only {sorted(t.value for t in IMPLEMENTED_RECOMMENDATION_TYPES)}"
        raise RecommendationError(msg)


def assert_production_recommendation_configuration(config: RecommendationConfig) -> None:
    """Fail closed on partial generator success in production orchestration."""
    if config.candidate_generation.continue_on_generator_failure:
        msg = (
            "production recommendation requires continue_on_generator_failure=False "
            "(partial generator success must not be silent)"
        )
        raise RecommendationError(msg)


def assert_production_recommendation_request(request: RecommendationRequest) -> None:
    """Apply production guardrails to a recommendation request."""
    assert_production_recommendation_type(request.recommendation_type)
    assert_production_recommendation_configuration(request.config)


def assert_no_experimental_recommendation_rankers() -> None:
    """Guardrail placeholder: production recommendation uses baseline ranker only (Phase 11.5)."""
    return


__all__ = [
    "assert_no_experimental_recommendation_rankers",
    "assert_production_recommendation_configuration",
    "assert_production_recommendation_request",
    "assert_production_recommendation_type",
]
