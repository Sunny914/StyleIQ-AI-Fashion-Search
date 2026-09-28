"""Recommendation offline evaluation (Phase 11.7)."""

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
from productiq.recommendation.evaluation.evaluator import (
    RecommendationSeedPipelineSnapshot,
    evaluate_recommendation_benchmark,
    evaluate_seed,
    evaluate_variant,
)
from productiq.recommendation.evaluation.result_schema import (
    RecommendationBenchmarkEvaluationResult,
    RecommendationEvaluationConfig,
    evaluation_result_to_dict,
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
