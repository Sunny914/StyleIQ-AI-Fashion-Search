"""Ranking layer public API (Phase 10.1).

Contracts load lazily to avoid coupling ranking imports to retrieval execution stacks.
"""

from __future__ import annotations

import importlib
from typing import Any

__all__ = [
    "BASELINE_RANKER_VERSION",
    "DEFAULT_RANKING_VERSION",
    "NORMALIZATION_SCHEMA_VERSION",
    "ORDERED_LTR_FEATURE_NAMES",
    "RANKING_DATASET_VERSION",
    "RANKING_EVALUATION_VERSION",
    "RANKING_FEATURE_SCHEMA_VERSION",
    "BaselineFeatureWeights",
    "BaselineRankingConfig",
    "BaselineScoreBreakdown",
    "InMemoryRankingProductContextProvider",
    "LTRTrainingConfig",
    "LTRBaselineBenchmarkEvaluator",
    "LTRBaselineBenchmarkEvaluationResult",
    "LTR_INFERENCE_VERSION",
    "NormalizedRankingFeatures",
    "RankedCandidate",
    "RankingBenchmarkEvaluationResult",
    "RankingBenchmarkEvaluator",
    "RankingCandidate",
    "RankingConfig",
    "RankingDataset",
    "RankingDatasetQueryGroup",
    "RankingDatasetRow",
    "RankingError",
    "RankingEvaluationConfig",
    "RankingFeatures",
    "RankingProductContext",
    "RankingProductContextProvider",
    "RankingRequest",
    "RankingResponse",
    "apply_ranking_top_k",
    "binary_relevance_labels_for_products",
    "build_ranking_dataset_from_query_groups",
    "deterministic_ranking_sort_key",
    "extract_features",
    "extract_features_for_request",
    "normalize_feature_rows",
    "normalize_features_for_query",
    "normalized_ranking_features_to_dict",
    "rank_candidates",
    "rank_candidates_with_feature_rows",
    "rank_candidates_with_ltr",
    "rank_candidates_with_ltr_feature_rows",
    "load_validated_ltr_artifact",
    "ranking_candidate_from_retrieval",
    "ranking_candidates_from_retrieval_response",
    "ranking_dataset_to_dict",
    "ranking_features_to_dict",
    "ranking_output_limit",
    "ranking_request_from_retrieval_response",
    "ranking_request_to_dict",
    "ranking_response_to_dict",
    "train_ltr_model",
    "validate_unique_ranking_product_ids",
]


def _lazy(module: str, *names: str) -> dict[str, tuple[str, str]]:
    return {name: (module, name) for name in names}


_LAZY_EXPORTS: dict[str, tuple[str, str]] = {}
_LAZY_EXPORTS.update(_lazy("productiq.exceptions", "RankingError"))
_LAZY_EXPORTS.update(
    _lazy(
        "productiq.ranking.config",
        "DEFAULT_RANKING_VERSION",
        "RankingConfig",
    )
)
_LAZY_EXPORTS.update(
    _lazy(
        "productiq.ranking.contracts",
        "RankedCandidate",
        "RankingCandidate",
        "RankingRequest",
        "RankingResponse",
        "ranking_request_to_dict",
        "ranking_response_to_dict",
    )
)
_LAZY_EXPORTS.update(
    _lazy(
        "productiq.ranking.adapters",
        "ranking_candidate_from_retrieval",
        "ranking_candidates_from_retrieval_response",
        "ranking_request_from_retrieval_response",
    )
)
_LAZY_EXPORTS.update(
    _lazy(
        "productiq.ranking.invariants",
        "apply_ranking_top_k",
        "deterministic_ranking_sort_key",
        "ranking_output_limit",
        "validate_unique_ranking_product_ids",
    )
)
_LAZY_EXPORTS.update(
    _lazy(
        "productiq.ranking.feature_schema",
        "RANKING_FEATURE_SCHEMA_VERSION",
        "RankingFeatures",
        "ranking_features_to_dict",
    )
)
_LAZY_EXPORTS.update(_lazy("productiq.ranking.product_context", "RankingProductContext"))
_LAZY_EXPORTS.update(
    _lazy(
        "productiq.ranking.product_context_provider",
        "InMemoryRankingProductContextProvider",
        "RankingProductContextProvider",
    )
)
_LAZY_EXPORTS.update(
    _lazy(
        "productiq.ranking.feature_extractor",
        "extract_features",
        "extract_features_for_request",
    )
)
_LAZY_EXPORTS.update(
    _lazy(
        "productiq.ranking.normalization_schema",
        "NORMALIZATION_SCHEMA_VERSION",
        "NormalizedRankingFeatures",
        "normalized_ranking_features_to_dict",
    )
)
_LAZY_EXPORTS.update(
    _lazy(
        "productiq.ranking.normalization",
        "normalize_feature_rows",
        "normalize_features_for_query",
    )
)
_LAZY_EXPORTS.update(
    _lazy(
        "productiq.ranking.dataset_schema",
        "RANKING_DATASET_VERSION",
        "RankingDataset",
        "RankingDatasetRow",
        "ranking_dataset_to_dict",
    )
)
_LAZY_EXPORTS.update(
    _lazy(
        "productiq.ranking.dataset_builder",
        "RankingDatasetQueryGroup",
        "build_ranking_dataset_from_query_groups",
    )
)
_LAZY_EXPORTS.update(
    _lazy(
        "productiq.ranking.benchmark_labels",
        "binary_relevance_labels_for_products",
    )
)
_LAZY_EXPORTS.update(
    _lazy(
        "productiq.ranking.baseline_config",
        "BASELINE_RANKER_VERSION",
        "BaselineFeatureWeights",
        "BaselineRankingConfig",
    )
)
_LAZY_EXPORTS.update(
    _lazy(
        "productiq.ranking.baseline_scoring",
        "BaselineScoreBreakdown",
        "compute_baseline_score",
    )
)
_LAZY_EXPORTS.update(
    _lazy(
        "productiq.ranking.baseline_ranker",
        "rank_candidates",
        "rank_candidates_with_feature_rows",
    )
)
_LAZY_EXPORTS.update(
    _lazy(
        "productiq.ranking.evaluation",
        "RANKING_EVALUATION_VERSION",
        "RankingBenchmarkEvaluator",
        "RankingBenchmarkEvaluationResult",
        "RankingEvaluationConfig",
        "evaluate_ranking_query",
    )
)
_LAZY_EXPORTS.update(
    _lazy(
        "productiq.ranking.ltr",
        "LTRTrainingConfig",
        "LTR_INFERENCE_VERSION",
        "LTRBaselineBenchmarkEvaluator",
        "LTRBaselineBenchmarkEvaluationResult",
        "ORDERED_LTR_FEATURE_NAMES",
        "load_validated_ltr_artifact",
        "rank_candidates_with_ltr",
        "rank_candidates_with_ltr_feature_rows",
        "train_ltr_model",
    )
)


def __getattr__(name: str) -> Any:
    if name not in _LAZY_EXPORTS:
        msg = f"module {__name__!r} has no attribute {name!r}"
        raise AttributeError(msg)
    module_name, attr_name = _LAZY_EXPORTS[name]
    module = importlib.import_module(module_name)
    return getattr(module, attr_name)


def __dir__() -> list[str]:
    return sorted(__all__)
