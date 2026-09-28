"""Ranking evaluation public API (Phase 10.6)."""

from productiq.ranking.evaluation.comparison import compare_ranking_evaluation_metrics
from productiq.ranking.evaluation.coverage import candidate_coverage_ratio
from productiq.ranking.evaluation.evaluator import RankingBenchmarkEvaluator, evaluate_ranking_query
from productiq.ranking.evaluation.schema import (
    RANKING_EVALUATION_VERSION,
    RankingBenchmarkEvaluationResult,
    RankingDiagnosticTag,
    RankingEvaluationComparison,
    RankingEvaluationConfig,
)

__all__ = [
    "RANKING_EVALUATION_VERSION",
    "RankingBenchmarkEvaluationResult",
    "RankingBenchmarkEvaluator",
    "RankingDiagnosticTag",
    "RankingEvaluationComparison",
    "RankingEvaluationConfig",
    "candidate_coverage_ratio",
    "compare_ranking_evaluation_metrics",
    "evaluate_ranking_query",
]
