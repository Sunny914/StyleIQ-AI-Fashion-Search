"""Offline ranking benchmark evaluation (Phase 10.6)."""

from __future__ import annotations

from productiq.exceptions.base import RankingError
from productiq.ranking.baseline_config import BASELINE_RANKER_VERSION
from productiq.ranking.evaluation.comparison import compare_ranking_evaluation_metrics
from productiq.ranking.evaluation.coverage import candidate_coverage_ratio
from productiq.ranking.evaluation.diagnostics import build_ranking_query_diagnostics
from productiq.ranking.evaluation.schema import (
    RANKING_EVALUATION_VERSION,
    RankingBenchmarkEvaluationResult,
    RankingEvaluationConfig,
    RankingEvaluationLineage,
    RankingQueryEvaluationResult,
)
from productiq.representation.query_contract import build_query_representation
from productiq.retrieval.contracts import RetrievalRequest
from productiq.retrieval.evaluation.dataset import LexicalEvaluationQuery, LexicalRetrievalBenchmark
from productiq.retrieval.evaluation.metrics import (
    normalize_retrieved_product_ids,
    validate_positive_k,
)
from productiq.retrieval.evaluation.unified_evaluator import (
    aggregate_query_results,
    evaluate_single_query,
)
from productiq.retrieval.production_pipeline import ProductionRetrievalPipeline
from productiq.retrieval.production_ranking_config import ProductionRankingStageConfig


def _evaluation_lists_for_query(
    *,
    rrf_ordered_product_ids: tuple[str, ...],
    baseline_ranked_product_ids: tuple[str, ...],
    evaluation_top_k: int,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    validate_positive_k(evaluation_top_k)
    rrf_list = normalize_retrieved_product_ids(
        rrf_ordered_product_ids,
        max_count=evaluation_top_k,
    )
    baseline_list = normalize_retrieved_product_ids(
        baseline_ranked_product_ids,
        max_count=evaluation_top_k,
    )
    return rrf_list, baseline_list


def evaluate_ranking_query(
    evaluation_query: LexicalEvaluationQuery,
    *,
    rrf_ordered_product_ids: tuple[str, ...],
    baseline_ranked_product_ids: tuple[str, ...],
    filtered_pool_product_ids: tuple[str, ...],
    config: RankingEvaluationConfig,
) -> RankingQueryEvaluationResult:
    """Evaluate one benchmark query for RRF-order vs baseline on the same filtered pool."""
    rrf_list, baseline_list = _evaluation_lists_for_query(
        rrf_ordered_product_ids=rrf_ordered_product_ids,
        baseline_ranked_product_ids=baseline_ranked_product_ids,
        evaluation_top_k=config.evaluation_top_k,
    )
    rrf_metrics = evaluate_single_query(
        evaluation_query,
        rrf_list,
        retrieval_top_k=config.evaluation_top_k,
        k_values=config.k_values,
        retrieval_candidate_count=len(rrf_list),
    )
    baseline_metrics = evaluate_single_query(
        evaluation_query,
        baseline_list,
        retrieval_top_k=config.evaluation_top_k,
        k_values=config.k_values,
        retrieval_candidate_count=len(baseline_list),
    )
    coverage = candidate_coverage_ratio(
        judged_relevant_product_ids=evaluation_query.relevant_product_ids,
        candidate_pool_product_ids=filtered_pool_product_ids,
    )
    diagnostics = build_ranking_query_diagnostics(
        judged_relevant_product_ids=evaluation_query.relevant_product_ids,
        candidate_pool_product_ids=filtered_pool_product_ids,
        evaluated_ranked_product_ids=baseline_list,
        evaluation_top_k=config.evaluation_top_k,
        first_relevant_rank=baseline_metrics.metrics.first_relevant_rank,
    )
    return RankingQueryEvaluationResult(
        query_id=evaluation_query.query_id,
        query_text=evaluation_query.query_text,
        category=evaluation_query.category,
        judged_relevant_count=rrf_metrics.judged_relevant_count,
        filtered_pool_candidate_count=len(filtered_pool_product_ids),
        candidate_coverage=coverage,
        rrf=rrf_metrics,
        baseline=baseline_metrics,
        diagnostics=diagnostics,
    )


class RankingBenchmarkEvaluator:
    """Evaluate fixed baseline ranking against RRF order on the lexical benchmark."""

    def __init__(self, config: RankingEvaluationConfig | None = None) -> None:
        self._config = config or RankingEvaluationConfig()

    @property
    def config(self) -> RankingEvaluationConfig:
        return self._config

    def evaluate_production_pipeline(
        self,
        benchmark: LexicalRetrievalBenchmark,
        pipeline: ProductionRetrievalPipeline,
    ) -> RankingBenchmarkEvaluationResult:
        if pipeline.config.candidate_pool_top_k != self._config.candidate_pool_top_k:
            msg = "pipeline candidate_pool_top_k must match RankingEvaluationConfig"
            raise RankingError(msg)
        if pipeline.config.candidate_pool_top_k < self._config.evaluation_top_k:
            msg = "candidate_pool_top_k must be >= evaluation_top_k"
            raise RankingError(msg)
        stage = pipeline.ranking_stage or ProductionRankingStageConfig()
        if not stage.enabled:
            msg = "baseline ranking must be enabled for ranking evaluation"
            raise RankingError(msg)
        if pipeline.product_context_provider is None:
            msg = "product_context_provider is required for ranking evaluation"
            raise RankingError(msg)

        per_query: list[RankingQueryEvaluationResult] = []
        version_lineage: RankingEvaluationLineage | None = None
        for evaluation_query in benchmark.queries:
            request = RetrievalRequest(
                query=build_query_representation(evaluation_query.query_text),
                top_k=self._config.evaluation_top_k,
            )
            bundle = pipeline.retrieve_ranked_evaluation_bundle(request)
            baseline_ids = tuple(
                row.product_id for row in bundle.ranked_search.ranking.ranked_candidates
            )
            row = evaluate_ranking_query(
                evaluation_query,
                rrf_ordered_product_ids=bundle.rrf_ordered_product_ids,
                baseline_ranked_product_ids=baseline_ids,
                filtered_pool_product_ids=bundle.filtered_pool_product_ids,
                config=self._config,
            )
            per_query.append(row)
            if version_lineage is None:
                ranked = bundle.ranked_search
                version_lineage = RankingEvaluationLineage(
                    benchmark_name=benchmark.benchmark_name,
                    benchmark_version=benchmark.benchmark_version,
                    evaluation_top_k=self._config.evaluation_top_k,
                    candidate_pool_top_k=self._config.candidate_pool_top_k,
                    k_values=self._config.k_values,
                    ranking_version=ranked.ranking.config.ranking_version,
                    feature_schema_version=ranked.feature_schema_version,
                    normalization_schema_version=ranked.normalization_schema_version,
                    ranking_pipeline_version=ranked.ranking_pipeline_version,
                )

        ordered = tuple(sorted(per_query, key=lambda item: item.query_id))
        rrf_rows = tuple(row.rrf for row in ordered)
        baseline_rows = tuple(row.baseline for row in ordered)
        rrf_aggregate = aggregate_query_results(rrf_rows, k_values=self._config.k_values)
        baseline_aggregate = aggregate_query_results(baseline_rows, k_values=self._config.k_values)
        lineage = version_lineage or RankingEvaluationLineage(
            benchmark_name=benchmark.benchmark_name,
            benchmark_version=benchmark.benchmark_version,
            evaluation_top_k=self._config.evaluation_top_k,
            candidate_pool_top_k=self._config.candidate_pool_top_k,
            k_values=self._config.k_values,
            ranking_version=BASELINE_RANKER_VERSION,
        )
        judged_total = sum(row.judged_relevant_count for row in ordered)
        return RankingBenchmarkEvaluationResult(
            evaluation_version=RANKING_EVALUATION_VERSION,
            benchmark_name=benchmark.benchmark_name,
            benchmark_version=benchmark.benchmark_version,
            query_count=len(ordered),
            total_judged_relevance_count=judged_total,
            evaluation_top_k=self._config.evaluation_top_k,
            candidate_pool_top_k=self._config.candidate_pool_top_k,
            k_values=self._config.k_values,
            rrf=rrf_aggregate,
            baseline=baseline_aggregate,
            per_query=ordered,
            comparison=compare_ranking_evaluation_metrics(
                rrf=rrf_aggregate,
                baseline=baseline_aggregate,
                k_values=self._config.k_values,
            ),
            lineage=lineage,
        )

    def evaluate_from_lists(
        self,
        benchmark: LexicalRetrievalBenchmark,
        *,
        rrf_by_query_id: dict[str, tuple[str, ...]],
        baseline_by_query_id: dict[str, tuple[str, ...]],
        pool_by_query_id: dict[str, tuple[str, ...]],
    ) -> RankingBenchmarkEvaluationResult:
        per_query: list[RankingQueryEvaluationResult] = []
        for evaluation_query in benchmark.queries:
            query_id = evaluation_query.query_id
            row = evaluate_ranking_query(
                evaluation_query,
                rrf_ordered_product_ids=rrf_by_query_id.get(query_id, ()),
                baseline_ranked_product_ids=baseline_by_query_id.get(query_id, ()),
                filtered_pool_product_ids=pool_by_query_id.get(query_id, ()),
                config=self._config,
            )
            per_query.append(row)
        ordered = tuple(sorted(per_query, key=lambda item: item.query_id))
        rrf_aggregate = aggregate_query_results(
            tuple(row.rrf for row in ordered),
            k_values=self._config.k_values,
        )
        baseline_aggregate = aggregate_query_results(
            tuple(row.baseline for row in ordered),
            k_values=self._config.k_values,
        )
        lineage = RankingEvaluationLineage(
            benchmark_name=benchmark.benchmark_name,
            benchmark_version=benchmark.benchmark_version,
            evaluation_top_k=self._config.evaluation_top_k,
            candidate_pool_top_k=self._config.candidate_pool_top_k,
            k_values=self._config.k_values,
            ranking_version=BASELINE_RANKER_VERSION,
        )
        judged_total = sum(row.judged_relevant_count for row in ordered)
        return RankingBenchmarkEvaluationResult(
            evaluation_version=RANKING_EVALUATION_VERSION,
            benchmark_name=benchmark.benchmark_name,
            benchmark_version=benchmark.benchmark_version,
            query_count=len(ordered),
            total_judged_relevance_count=judged_total,
            evaluation_top_k=self._config.evaluation_top_k,
            candidate_pool_top_k=self._config.candidate_pool_top_k,
            k_values=self._config.k_values,
            rrf=rrf_aggregate,
            baseline=baseline_aggregate,
            per_query=ordered,
            comparison=compare_ranking_evaluation_metrics(
                rrf=rrf_aggregate,
                baseline=baseline_aggregate,
                k_values=self._config.k_values,
            ),
            lineage=lineage,
        )


__all__ = [
    "RankingBenchmarkEvaluator",
    "evaluate_ranking_query",
]
