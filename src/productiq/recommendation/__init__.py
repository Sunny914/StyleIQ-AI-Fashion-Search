"""Recommendation layer public API (Phase 11.1).

Contracts load lazily to avoid coupling recommendation imports to retrieval or ranking stacks.
"""

from __future__ import annotations

import importlib
from typing import Any

__all__ = [
    "DEFAULT_MAX_RECOMMENDATION_TOP_K",
    "DEFAULT_RECOMMENDATION_CONTRACT_VERSION",
    "IMPLEMENTED_RECOMMENDATION_TYPES",
    "SUPPORTED_RECOMMENDATION_TYPES",
    "RankedRecommendation",
    "RecommendationCandidate",
    "RecommendationCandidateSource",
    "RecommendationConfig",
    "RecommendationError",
    "RecommendationRequest",
    "RecommendationResponse",
    "RecommendationType",
    "apply_recommendation_top_k",
    "deterministic_recommendation_sort_key",
    "recommendation_output_limit",
    "recommendation_request_to_dict",
    "recommendation_response_to_dict",
    "validate_recommendation_request_for_pipeline",
    "validate_recommendation_response_invariants",
    "validate_recommendation_type_implemented",
    "validate_seed_product_excluded",
]


def _lazy(module: str, *names: str) -> dict[str, tuple[str, str]]:
    return {name: (module, name) for name in names}


_LAZY_EXPORTS: dict[str, tuple[str, str]] = {}
_LAZY_EXPORTS.update(_lazy("productiq.exceptions", "RecommendationError"))
_LAZY_EXPORTS.update(
    _lazy(
        "productiq.recommendation.config",
        "DEFAULT_MAX_RECOMMENDATION_TOP_K",
        "DEFAULT_RECOMMENDATION_CONTRACT_VERSION",
        "RecommendationConfig",
    )
)
_LAZY_EXPORTS.update(
    _lazy(
        "productiq.recommendation.contracts",
        "IMPLEMENTED_RECOMMENDATION_TYPES",
        "RankedRecommendation",
        "RecommendationCandidate",
        "RecommendationCandidateSource",
        "RecommendationRequest",
        "RecommendationResponse",
        "RecommendationType",
        "SUPPORTED_RECOMMENDATION_TYPES",
        "recommendation_request_to_dict",
        "recommendation_response_to_dict",
    )
)
_LAZY_EXPORTS.update(
    _lazy(
        "productiq.recommendation.invariants",
        "apply_recommendation_top_k",
        "deterministic_recommendation_sort_key",
        "recommendation_output_limit",
        "validate_recommendation_request_for_pipeline",
        "validate_recommendation_response_invariants",
        "validate_recommendation_type_implemented",
        "validate_seed_product_excluded",
    )
)


def __getattr__(name: str) -> Any:
    if name not in _LAZY_EXPORTS:
        msg = f"module {__name__!r} has no attribute {name!r}"
        raise AttributeError(msg)
    module_path, attr = _LAZY_EXPORTS[name]
    module = importlib.import_module(module_path)
    value = getattr(module, attr)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
