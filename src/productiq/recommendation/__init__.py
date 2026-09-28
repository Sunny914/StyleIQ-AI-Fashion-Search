"""Recommendation layer public API (Phase 11.1).

Contracts load lazily to avoid coupling recommendation imports to retrieval or ranking stacks.
"""

from __future__ import annotations

import importlib
from typing import Any

__all__ = [
    "CONTENT_SIMILARITY_SCHEMA_VERSION",
    "DEFAULT_CANDIDATE_POOL_TOP_K",
    "DEFAULT_MAX_RECOMMENDATION_TOP_K",
    "DEFAULT_RECOMMENDATION_CONTRACT_VERSION",
    "IMPLEMENTED_RECOMMENDATION_TYPES",
    "ORDERED_RECOMMENDATION_FEATURE_NAMES",
    "RECOMMENDATION_FEATURE_SCHEMA_VERSION",
    "SUPPORTED_RECOMMENDATION_TYPES",
    "AttributeRecommendationCandidateGenerator",
    "BM25RecommendationCandidateGenerator",
    "BaselineRecommendationRanker",
    "BaselineRecommendationRankerConfig",
    "BaselineRecommendationScoreBreakdown",
    "ContentSimilarity",
    "ContentSimilarityEngine",
    "InMemoryProductEmbeddingProvider",
    "ProductEmbeddingProvider",
    "RankedRecommendation",
    "RecommendationCandidate",
    "RecommendationCandidateGenerationResult",
    "RecommendationCandidateGenerator",
    "RecommendationCandidateSource",
    "RecommendationConfig",
    "RecommendationError",
    "RecommendationEvaluationConfig",
    "RecommendationFeatureMatrix",
    "RecommendationFeatures",
    "RecommendationPipeline",
    "RecommendationPipelineExecutionMetadata",
    "RecommendationPipelineObservation",
    "RecommendationPipelineResult",
    "RecommendationProductContext",
    "RecommendationProductContextProvider",
    "RecommendationRequest",
    "RecommendationResponse",
    "RecommendationSeedPipelineSnapshot",
    "RecommendationSelectionConfig",
    "RecommendationSelectionContext",
    "RecommendationSelectionResult",
    "RecommendationType",
    "StructuredProductSimilarity",
    "VectorRecommendationCandidateGenerator",
    "apply_candidate_pool_top_k",
    "apply_recommendation_top_k",
    "build_recommendation_feature_matrix",
    "content_similarity_to_dict",
    "deterministic_recommendation_sort_key",
    "evaluate_recommendation_benchmark",
    "evaluation_result_to_dict",
    "extract_features",
    "extract_features_for_candidates",
    "generate_recommendation_candidates",
    "load_recommendation_benchmark",
    "rank_recommendations",
    "rank_recommendations_for_request",
    "recommendation_output_limit",
    "recommendation_request_to_dict",
    "recommendation_response_to_dict",
    "score_recommendation_features",
    "select_recommendations",
    "select_recommendations_for_request",
    "select_recommendations_with_diagnostics",
    "validate_pipeline_guardrail_response",
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
        "DEFAULT_CANDIDATE_POOL_TOP_K",
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
        "RecommendationCandidateGenerationResult",
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
        "productiq.recommendation.candidate_generation",
        "apply_candidate_pool_top_k",
        "generate_recommendation_candidates",
    )
)
_LAZY_EXPORTS.update(
    _lazy(
        "productiq.recommendation.generators",
        "AttributeRecommendationCandidateGenerator",
        "BM25RecommendationCandidateGenerator",
        "RecommendationCandidateGenerator",
        "VectorRecommendationCandidateGenerator",
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
_LAZY_EXPORTS.update(
    _lazy(
        "productiq.recommendation.similarity_schema",
        "CONTENT_SIMILARITY_SCHEMA_VERSION",
        "ContentSimilarity",
        "StructuredProductSimilarity",
        "content_similarity_to_dict",
    )
)
_LAZY_EXPORTS.update(
    _lazy(
        "productiq.recommendation.catalog_embeddings",
        "InMemoryProductEmbeddingProvider",
        "ProductEmbeddingProvider",
    )
)
_LAZY_EXPORTS.update(_lazy("productiq.recommendation.content_similarity_engine", "ContentSimilarityEngine"))
_LAZY_EXPORTS.update(
    _lazy(
        "productiq.recommendation.feature_schema",
        "ORDERED_RECOMMENDATION_FEATURE_NAMES",
        "RECOMMENDATION_FEATURE_SCHEMA_VERSION",
        "RecommendationFeatures",
        "recommendation_features_to_dict",
    )
)
_LAZY_EXPORTS.update(_lazy("productiq.recommendation.product_context", "RecommendationProductContext"))
_LAZY_EXPORTS.update(
    _lazy(
        "productiq.recommendation.feature_extractor",
        "extract_features",
        "extract_features_for_candidates",
    )
)
_LAZY_EXPORTS.update(
    _lazy(
        "productiq.recommendation.feature_matrix",
        "RecommendationFeatureMatrix",
        "build_recommendation_feature_matrix",
    )
)
_LAZY_EXPORTS.update(
    _lazy(
        "productiq.recommendation.baseline_ranker_config",
        "BaselineRecommendationRankerConfig",
    )
)
_LAZY_EXPORTS.update(
    _lazy(
        "productiq.recommendation.baseline_scoring",
        "BaselineRecommendationScoreBreakdown",
        "score_recommendation_features",
    )
)
_LAZY_EXPORTS.update(
    _lazy(
        "productiq.recommendation.baseline_ranker",
        "BaselineRecommendationRanker",
        "rank_recommendations",
        "rank_recommendations_for_request",
    )
)
_LAZY_EXPORTS.update(
    _lazy(
        "productiq.recommendation.selection_config",
        "RecommendationSelectionConfig",
    )
)
_LAZY_EXPORTS.update(_lazy("productiq.recommendation.selection_context", "RecommendationSelectionContext"))
_LAZY_EXPORTS.update(
    _lazy(
        "productiq.recommendation.selection_diagnostics",
        "RecommendationSelectionResult",
    )
)
_LAZY_EXPORTS.update(
    _lazy(
        "productiq.recommendation.recommendation_selection",
        "select_recommendations",
        "select_recommendations_for_request",
        "select_recommendations_with_diagnostics",
    )
)
_LAZY_EXPORTS.update(
    _lazy(
        "productiq.recommendation.evaluation",
        "RecommendationEvaluationConfig",
        "RecommendationSeedPipelineSnapshot",
        "evaluate_recommendation_benchmark",
        "evaluation_result_to_dict",
        "load_recommendation_benchmark",
    )
)
_LAZY_EXPORTS.update(
    _lazy(
        "productiq.recommendation.recommendation_pipeline",
        "RecommendationPipeline",
    )
)
_LAZY_EXPORTS.update(
    _lazy(
        "productiq.recommendation.recommendation_pipeline_config",
        "RecommendationPipelineExecutionMetadata",
        "RecommendationPipelineResult",
    )
)
_LAZY_EXPORTS.update(
    _lazy(
        "productiq.recommendation.recommendation_product_context_provider",
        "InMemoryRecommendationProductContextProvider",
        "RecommendationProductContextProvider",
    )
)
_LAZY_EXPORTS.update(
    _lazy(
        "productiq.recommendation.hardening",
        "RecommendationPipelineObservation",
        "assert_production_recommendation_request",
        "observe_pipeline_execution",
        "validate_pipeline_guardrail_response",
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
