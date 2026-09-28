"""Tests for Phase 10.6 ranking evaluation."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from productiq.exceptions import RankingError
from productiq.ranking.baseline_config import BaselineFeatureWeights, BaselineRankingConfig
from productiq.ranking.evaluation import (
    RankingBenchmarkEvaluator,
    RankingDiagnosticTag,
    RankingEvaluationConfig,
    candidate_coverage_ratio,
    compare_ranking_evaluation_metrics,
    evaluate_ranking_query,
)
from productiq.ranking.evaluation.schema import RANKING_EVALUATION_VERSION
from productiq.retrieval.contracts import RetrievalRequest, RetrievalResponse
from productiq.retrieval.evaluation.dataset import LexicalEvaluationQuery, LexicalRetrievalBenchmark
from productiq.retrieval.evaluation.metrics import precision_at_k, recall_at_k
from productiq.retrieval.evaluation.unified_evaluator import aggregate_query_results
from productiq.retrieval.production_config import ProductionRetrievalConfig
from productiq.retrieval.production_pipeline import ProductionRetrievalPipeline
from productiq.retrieval.production_ranking_config import ProductionRankingStageConfig
from productiq.retrieval.rrf_fusion import fused_candidate_from_rrf
from tests.retrieval.test_production_ranking_integration import _context_provider, _ranked_pipeline


def _benchmark(*queries: LexicalEvaluationQuery) -> LexicalRetrievalBenchmark:
    return LexicalRetrievalBenchmark(
        benchmark_name="productiq_lexical_retrieval_v1",
        benchmark_version="1.0.0",
        catalog_artifact="resources/processed/product_representations.parquet",
        methodology="test",
        limitations="test",
        queries=queries,
    )


def _query(
    query_id: str = "q1",
    relevant: tuple[str, ...] = ("R1", "R2"),
) -> LexicalEvaluationQuery:
    return LexicalEvaluationQuery(
        query_id=query_id,
        query_text="demo query",
        category="demo",
        relevant_product_ids=relevant,
    )


def _eval_config(**overrides: object) -> RankingEvaluationConfig:
    base: dict[str, object] = {
        "evaluation_top_k": 50,
        "k_values": (1, 5, 10, 20, 50),
        "candidate_pool_top_k": 50,
    }
    base.update(overrides)
    return RankingEvaluationConfig(**base)  # type: ignore[arg-type]


def test_mrr_known_example() -> None:
    query = _query(relevant=("B",))
    row = evaluate_ranking_query(
        query,
        rrf_ordered_product_ids=("X", "B", "Y"),
        baseline_ranked_product_ids=("B", "X", "Y"),
        filtered_pool_product_ids=("X", "B", "Y"),
        config=_eval_config(),
    )
    assert row.rrf.metrics.reciprocal_rank == pytest.approx(0.5)
    assert row.baseline.metrics.reciprocal_rank == pytest.approx(1.0)


def test_precision_at_k_known_example() -> None:
    query = _query(relevant=("R1", "R2"))
    row = evaluate_ranking_query(
        query,
        rrf_ordered_product_ids=("R1", "X", "R2"),
        baseline_ranked_product_ids=("R1", "R2", "X"),
        filtered_pool_product_ids=("R1", "X", "R2"),
        config=_eval_config(),
    )
    assert row.baseline.metrics.precision_at_k[5] == pytest.approx(2 / 3)


def test_recall_at_k_known_example() -> None:
    query = _query(relevant=("R1", "R2"))
    row = evaluate_ranking_query(
        query,
        rrf_ordered_product_ids=("R1", "X", "Y"),
        baseline_ranked_product_ids=("R1", "R2", "X"),
        filtered_pool_product_ids=("R1", "X", "R2"),
        config=_eval_config(),
    )
    assert row.baseline.metrics.recall_at_k[5] == pytest.approx(1.0)


def test_empty_ranked_result() -> None:
    query = _query()
    row = evaluate_ranking_query(
        query,
        rrf_ordered_product_ids=(),
        baseline_ranked_product_ids=(),
        filtered_pool_product_ids=(),
        config=_eval_config(),
    )
    assert row.baseline.metrics.reciprocal_rank == 0.0
    assert row.baseline.metrics.precision_at_k[1] == 0.0


def test_no_relevant_retrieved() -> None:
    query = _query(relevant=("R1",))
    row = evaluate_ranking_query(
        query,
        rrf_ordered_product_ids=("X", "Y"),
        baseline_ranked_product_ids=("X", "Y"),
        filtered_pool_product_ids=("R1", "X", "Y"),
        config=_eval_config(),
    )
    assert row.baseline.metrics.first_relevant_rank is None
    assert RankingDiagnosticTag.RELEVANT_RETRIEVED_BUT_RANKED_LOW in row.diagnostics.diagnostic_tags


def test_k_larger_than_result_length() -> None:
    retrieved = ("R1",)
    relevant = ("R1",)
    assert precision_at_k(retrieved, relevant, k=50) == pytest.approx(1.0)
    assert recall_at_k(retrieved, relevant, k=50) == pytest.approx(1.0)


def test_duplicate_retrieved_ids_deduped_in_metrics() -> None:
    query = _query(relevant=("R1",))
    row = evaluate_ranking_query(
        query,
        rrf_ordered_product_ids=("R1", "R1", "X"),
        baseline_ranked_product_ids=("R1", "R1", "X"),
        filtered_pool_product_ids=("R1", "X"),
        config=_eval_config(),
    )
    assert row.baseline.metrics.reciprocal_rank == pytest.approx(1.0)


def test_candidate_coverage() -> None:
    assert candidate_coverage_ratio(
        judged_relevant_product_ids=("A", "B", "C"),
        candidate_pool_product_ids=("A", "X"),
    ) == pytest.approx(1 / 3)
    assert candidate_coverage_ratio(judged_relevant_product_ids=(), candidate_pool_product_ids=("A",)) is None


def test_relevant_not_in_candidate_pool_diagnostic() -> None:
    query = _query(relevant=("MISSING", "IN_POOL"))
    row = evaluate_ranking_query(
        query,
        rrf_ordered_product_ids=("IN_POOL",),
        baseline_ranked_product_ids=("IN_POOL",),
        filtered_pool_product_ids=("IN_POOL",),
        config=_eval_config(),
    )
    assert RankingDiagnosticTag.RELEVANT_NOT_IN_CANDIDATE_POOL in row.diagnostics.diagnostic_tags
    assert row.diagnostics.relevant_missing_from_pool_product_ids == ("MISSING",)


def test_aggregate_and_comparison() -> None:
    benchmark = _benchmark(
        _query("q1", ("R1",)),
        _query("q2", ("R2",)),
    )
    evaluator = RankingBenchmarkEvaluator(_eval_config())
    result = evaluator.evaluate_from_lists(
        benchmark,
        rrf_by_query_id={
            "q1": ("X", "R1"),
            "q2": ("R2", "Y"),
        },
        baseline_by_query_id={
            "q1": ("R1", "X"),
            "q2": ("R2", "Y"),
        },
        pool_by_query_id={
            "q1": ("X", "R1"),
            "q2": ("R2", "Y"),
        },
    )
    assert result.query_count == 2
    assert result.comparison.mrr.delta == pytest.approx(
        result.baseline.mrr - result.rrf.mrr,
    )
    assert result.comparison.precision_at_k[1].rrf == pytest.approx(0.5)
    assert result.comparison.precision_at_k[1].baseline == pytest.approx(1.0)


def test_deterministic_repeated_evaluation() -> None:
    benchmark = _benchmark(_query("q1", ("A", "B")))
    evaluator = RankingBenchmarkEvaluator(_eval_config())
    kwargs = {
        "rrf_by_query_id": {"q1": ("A", "B", "C")},
        "baseline_by_query_id": {"q1": ("B", "A", "C")},
        "pool_by_query_id": {"q1": ("A", "B", "C")},
    }
    first = evaluator.evaluate_from_lists(benchmark, **kwargs)
    second = evaluator.evaluate_from_lists(benchmark, **kwargs)
    assert first == second


def test_benchmark_metadata_and_versions() -> None:
    benchmark = _benchmark(_query())
    evaluator = RankingBenchmarkEvaluator(_eval_config())
    result = evaluator.evaluate_from_lists(
        benchmark,
        rrf_by_query_id={"q1": ("R1",)},
        baseline_by_query_id={"q1": ("R1",)},
        pool_by_query_id={"q1": ("R1",)},
    )
    assert result.benchmark_name == "productiq_lexical_retrieval_v1"
    assert result.evaluation_version == RANKING_EVALUATION_VERSION
    assert result.lineage.ranking_version == "10.4.0"


def test_production_pipeline_integration_path() -> None:
    weights = BaselineFeatureWeights(
        **{name: 0.0 for name in BaselineFeatureWeights.model_fields}
        | {"vector_similarity": 1.0}
    )
    stage = ProductionRankingStageConfig(
        baseline_config=BaselineRankingConfig(weights=weights),
    )
    pipeline, _rrf, _catalog = _ranked_pipeline(
        ranking=("HIGH", "LOW"),
        pool_top_k=50,
        product_overrides={"HIGH": {}, "LOW": {}},
        ranking_stage=stage,
    )

    @dataclass
    class VectorAwareRRF:
        def retrieve(self, request: RetrievalRequest) -> RetrievalResponse:
            candidates = (
                fused_candidate_from_rrf(
                    "HIGH",
                    fusion_score=0.95,
                    bm25_rank=1,
                    vector_rank=2,
                    bm25_score=1.0,
                    vector_score=0.1,
                ),
                fused_candidate_from_rrf(
                    "LOW",
                    fusion_score=0.5,
                    bm25_rank=2,
                    vector_rank=1,
                    bm25_score=0.5,
                    vector_score=0.95,
                ),
            )
            return RetrievalResponse(candidates=candidates[: request.top_k], metadata=None)

    provider = _context_provider(HIGH={}, LOW={})
    eval_pipeline = ProductionRetrievalPipeline(
        rrf_retriever=VectorAwareRRF(),
        catalog_filter=pipeline.catalog_filter,
        config=ProductionRetrievalConfig(candidate_pool_top_k=50),
        product_context_provider=provider,
        ranking_stage=stage,
    )
    benchmark = _benchmark(_query("q_demo", ("LOW",)))
    evaluator = RankingBenchmarkEvaluator(_eval_config())
    result = evaluator.evaluate_production_pipeline(benchmark, eval_pipeline)
    assert result.baseline.mrr >= result.rrf.mrr
    assert result.lineage.feature_schema_version == "10.2.0"
    assert result.lineage.normalization_schema_version == "10.3.0"


def test_pipeline_config_mismatch_raises() -> None:
    pipeline, _, _ = _ranked_pipeline(ranking=("P1",), pool_top_k=10)
    evaluator = RankingBenchmarkEvaluator(_eval_config(candidate_pool_top_k=50))
    with pytest.raises(RankingError, match="candidate_pool_top_k"):
        evaluator.evaluate_production_pipeline(_benchmark(_query()), pipeline)


def test_compare_ranking_metrics_requires_matching_k() -> None:
    rrf = aggregate_query_results(
        (
            evaluate_ranking_query(
                _query(),
                rrf_ordered_product_ids=("R1",),
                baseline_ranked_product_ids=("R1",),
                filtered_pool_product_ids=("R1",),
                config=_eval_config(k_values=(1, 5)),
            ).rrf,
        ),
        k_values=(1, 5),
    )
    baseline = aggregate_query_results(
        (
            evaluate_ranking_query(
                _query(),
                rrf_ordered_product_ids=("R1",),
                baseline_ranked_product_ids=("R1",),
                filtered_pool_product_ids=("R1",),
                config=_eval_config(k_values=(1, 10)),
            ).baseline,
        ),
        k_values=(1, 10),
    )
    with pytest.raises(ValueError):
        compare_ranking_evaluation_metrics(rrf=rrf, baseline=baseline, k_values=(1, 5))
