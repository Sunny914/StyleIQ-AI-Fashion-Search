"""Recommendation offline evaluation (Phase 11.7)."""

from __future__ import annotations

import importlib
from typing import Any

from productiq.recommendation.evaluation.benchmark_loader import load_recommendation_benchmark
from productiq.recommendation.evaluation.benchmark_schema import (
    RECOMMENDATION_BENCHMARK_FILENAME,
    RECOMMENDATION_BENCHMARK_NAME,
    RECOMMENDATION_BENCHMARK_VERSION,
    RECOMMENDATION_EVALUATION_VERSION,
    RECOMMENDATION_VARIANT_BASELINE_11_5,
    RECOMMENDATION_VARIANT_BASELINE_11_5_PLUS_SELECTION_11_6,
    RecommendationBenchmark,
    RecommendationBenchmarkCase,
    RelevanceJudgment,
)
from productiq.recommendation.evaluation.result_schema import (
    RecommendationBenchmarkEvaluationResult,
    RecommendationEvaluationConfig,
    evaluation_result_to_dict,
)

_LAZY_EVALUATOR_EXPORTS: frozenset[str] = frozenset(
    {
        "RecommendationSeedPipelineSnapshot",
        "evaluate_recommendation_benchmark",
        "evaluate_seed",
        "evaluate_variant",
    }
)

__all__ = [
    "RECOMMENDATION_BENCHMARK_FILENAME",
    "RECOMMENDATION_BENCHMARK_NAME",
    "RECOMMENDATION_BENCHMARK_VERSION",
    "RECOMMENDATION_EVALUATION_VERSION",
    "RECOMMENDATION_VARIANT_BASELINE_11_5",
    "RECOMMENDATION_VARIANT_BASELINE_11_5_PLUS_SELECTION_11_6",
    "RecommendationBenchmark",
    "RecommendationBenchmarkCase",
    "RecommendationBenchmarkEvaluationResult",
    "RecommendationEvaluationConfig",
    "RecommendationSeedPipelineSnapshot",
    "RelevanceJudgment",
    "evaluate_recommendation_benchmark",
    "evaluate_seed",
    "evaluate_variant",
    "evaluation_result_to_dict",
    "load_recommendation_benchmark",
]


def __getattr__(name: str) -> Any:
    if name in _LAZY_EVALUATOR_EXPORTS:
        evaluator = importlib.import_module("productiq.recommendation.evaluation.evaluator")
        return getattr(evaluator, name)
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
