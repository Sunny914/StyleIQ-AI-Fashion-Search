"""Tests for Phase 11.7 recommendation evaluation."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from productiq.exceptions import RecommendationError
from productiq.recommendation.contracts import (
    RankedRecommendation,
    RecommendationCandidate,
    RecommendationCandidateSource,
)
from productiq.recommendation.evaluation.benchmark_loader import load_recommendation_benchmark
from productiq.recommendation.evaluation.benchmark_schema import (
    RECOMMENDATION_BENCHMARK_FILENAME,
    RecommendationBenchmark,
    RecommendationBenchmarkCase,
    RelevanceJudgment,
)
from productiq.recommendation.evaluation.evaluator import (
    RecommendationSeedPipelineSnapshot,
    evaluate_recommendation_benchmark,
    evaluate_seed,
)
from productiq.recommendation.evaluation.metrics import (
    hit_rate_at_k,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
    shortfall_metrics,
    unique_ratio,
)
from productiq.recommendation.evaluation.result_schema import RecommendationEvaluationConfig
from productiq.retrieval.evaluation.metrics import reciprocal_rank


def _ranked(product_id: str, rank: int, score: float) -> RankedRecommendation:
    return RankedRecommendation(
        product_id=product_id,
        rank=rank,
        recommendation_score=score,
        candidate=RecommendationCandidate(
            product_id=product_id,
            sources=(RecommendationCandidateSource.VECTOR,),
            candidate_generation_score=score,
        ),
    )


class TestBenchmarkContract:
    def test_loads_repository_benchmark(self) -> None:
        path = Path("resources/evaluation") / RECOMMENDATION_BENCHMARK_FILENAME
        benchmark = load_recommendation_benchmark(path)
        assert len(benchmark.cases) == 20
        assert benchmark.metadata.benchmark_name == "productiq_recommendation_v1"

    def test_rejects_seed_in_judgments(self) -> None:
        with pytest.raises(ValidationError):
            RecommendationBenchmarkCase(
                seed_product_id="S1",
                seed_category="test",
                methodology_note="note",
                relevance_judgments=(RelevanceJudgment(product_id="S1", grade=3),),
            )

    def test_rejects_invalid_grade(self) -> None:
        with pytest.raises(ValidationError):
            RelevanceJudgment(product_id="P1", grade=4)


class TestMetricDefinitions:
    def test_precision_denominator(self) -> None:
        assert precision_at_k(("A", "B"), {"A"}, k=5) == pytest.approx(0.5)

    def test_recall_against_judged_set(self) -> None:
        assert recall_at_k(("A", "X"), {"A", "B"}, k=5) == pytest.approx(0.5)

    def test_hit_rate(self) -> None:
        grades = {"A": 3, "B": 1}
        assert hit_rate_at_k(("X", "A"), grades, k=2, min_relevant_grade=2) == 1.0
        assert hit_rate_at_k(("X", "B"), grades, k=2, min_relevant_grade=2) == 0.0

    def test_mrr_no_relevant(self) -> None:
        assert reciprocal_rank(("X",), {"A"})[0] == 0.0

    def test_ndcg_graded(self) -> None:
        grades = {"A": 3, "B": 2, "C": 0}
        value = ndcg_at_k(("A", "C"), grades, k=2)
        assert value is not None
        assert 0.0 < value <= 1.0

    def test_shortfall(self) -> None:
        assert shortfall_metrics(requested_top_k=10, returned_count=7) == (3, 0.3)

    def test_unique_ratio(self) -> None:
        assert unique_ratio(["a", "a", "b"]) == pytest.approx(2 / 3)


class TestSeedEvaluation:
    def test_evaluate_seed_preserves_scores(self) -> None:
        case = RecommendationBenchmarkCase(
            seed_product_id="S1",
            seed_category="test",
            methodology_note="note",
            relevance_judgments=(
                RelevanceJudgment(product_id="P1", grade=3),
                RelevanceJudgment(product_id="P2", grade=2),
            ),
        )
        snapshot = RecommendationSeedPipelineSnapshot(
            seed_product_id="S1",
            requested_top_k=2,
            candidate_pool_product_ids=("P1", "P2", "P3"),
            ranked_recommendations=(
                _ranked("P1", 1, 0.91),
                _ranked("P2", 2, 0.87),
            ),
            final_recommendations=(
                _ranked("P1", 1, 0.91),
                _ranked("P2", 2, 0.87),
            ),
        )
        config = RecommendationEvaluationConfig(k_values=(1, 2), evaluation_top_k=2)
        metrics = evaluate_seed(
            case,
            snapshot,
            config=config,
            use_final_recommendations=True,
        )
        assert metrics.precision_at_k[2] == pytest.approx(1.0)
        assert metrics.recall_at_k[2] == pytest.approx(1.0)
        assert metrics.returned_count == 2
        assert metrics.shortfall_count == 0

    def test_compare_variants_deterministic(self) -> None:
        case = RecommendationBenchmarkCase(
            seed_product_id="S1",
            seed_category="test",
            methodology_note="note",
            relevance_judgments=(RelevanceJudgment(product_id="P1", grade=3),),
        )
        benchmark = RecommendationBenchmark(
            metadata=load_recommendation_benchmark(
                Path("resources/evaluation") / RECOMMENDATION_BENCHMARK_FILENAME
            ).metadata,
            cases=(case,),
        )
        snapshot = RecommendationSeedPipelineSnapshot(
            seed_product_id="S1",
            requested_top_k=3,
            candidate_pool_product_ids=("P1",),
            ranked_recommendations=(
                _ranked("P1", 1, 0.9),
                _ranked("P2", 2, 0.1),
            ),
            final_recommendations=(_ranked("P1", 1, 0.9),),
        )
        snapshots = {"S1": snapshot}
        config = RecommendationEvaluationConfig(k_values=(1, 2), evaluation_top_k=2)
        first = evaluate_recommendation_benchmark(benchmark, snapshots, config=config)
        second = evaluate_recommendation_benchmark(benchmark, snapshots, config=config)
        assert first.comparison.mrr_delta == second.comparison.mrr_delta

    def test_missing_snapshot_raises(self) -> None:
        path = Path("resources/evaluation") / RECOMMENDATION_BENCHMARK_FILENAME
        benchmark = load_recommendation_benchmark(path)
        with pytest.raises(RecommendationError, match="missing pipeline snapshot"):
            evaluate_recommendation_benchmark(benchmark, {})
