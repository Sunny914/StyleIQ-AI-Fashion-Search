"""Offline baseline vs LTR benchmark evaluation (Phase 10.8)."""

from __future__ import annotations

from productiq.exceptions.base import RankingError
from productiq.ranking.adapters import ranking_request_from_retrieval_response
from productiq.ranking.baseline_config import BASELINE_RANKER_VERSION, BaselineRankingConfig
from productiq.ranking.baseline_ranker import rank_candidates
from productiq.ranking.evaluation.coverage import candidate_coverage_ratio
from productiq.ranking.evaluation.diagnostics import build_ranking_query_diagnostics
from productiq.ranking.evaluation.evaluator import _evaluation_lists_for_query
from productiq.ranking.evaluation.schema import RankingEvaluationConfig
from productiq.ranking.feature_extractor import extract_features_for_request
from productiq.ranking.ltr.artifact import LTRModelArtifact
from productiq.ranking.ltr.comparison.comparison import compare_baseline_ltr_metrics
from productiq.ranking.ltr.comparison.schema import (
    LTRBaselineBenchmarkEvaluationResult,
    LTRBaselineEvaluationLineage,
    LTRBaselineQueryEvaluationResult,
)
from productiq.ranking.ltr.inference import rank_candidates_with_ltr
from productiq.ranking.ltr.inference_config import LTR_INFERENCE_VERSION
from productiq.ranking.normalization import normalize_features_for_query
from productiq.ranking.product_context_provider import RankingProductContextProvider
from productiq.representation.query_contract import build_query_representation
from productiq.retrieval.contracts import RetrievalCandidate, RetrievalRequest, RetrievalResponse
from productiq.retrieval.evaluation.dataset import LexicalEvaluationQuery, LexicalRetrievalBenchmark
from productiq.retrieval.evaluation.unified_evaluator import (
    aggregate_query_results,
    evaluate_single_query,
)
from productiq.retrieval.production_pipeline import ProductionRetrievalPipeline
from productiq.retrieval.production_ranking_config import ProductionRankingStageConfig


def evaluate_baseline_vs_ltr_query(
    evaluation_query: LexicalEvaluationQuery,
    *,
    baseline_ranked_product_ids: tuple[str, ...],
    ltr_ranked_product_ids: tuple[str, ...],
    filtered_pool_product_ids: tuple[str, ...],
    config: RankingEvaluationConfig,
) -> LTRBaselineQueryEvaluationResult:
    """Evaluate one benchmark query for baseline vs LTR on the same filtered pool."""
    baseline_list, _ = _evaluation_lists_for_query(
        rrf_ordered_product_ids=baseline_ranked_product_ids,
        baseline_ranked_product_ids=baseline_ranked_product_ids,
        evaluation_top_k=config.evaluation_top_k,
    )
    _, ltr_list = _evaluation_lists_for_query(
        rrf_ordered_product_ids=ltr_ranked_product_ids,
        baseline_ranked_product_ids=ltr_ranked_product_ids,
        evaluation_top_k=config.evaluation_top_k,
    )
    baseline_metrics = evaluate_single_query(
        evaluation_query,
        baseline_list,
        retrieval_top_k=config.evaluation_top_k,
        k_values=config.k_values,
        retrieval_candidate_count=len(baseline_list),
    )
    ltr_metrics = evaluate_single_query(
        evaluation_query,
        ltr_list,
        retrieval_top_k=config.evaluation_top_k,
        k_values=config.k_values,
        retrieval_candidate_count=len(ltr_list),
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
    return LTRBaselineQueryEvaluationResult(
        query_id=evaluation_query.query_id,
        query_text=evaluation_query.query_text,
        category=evaluation_query.category,
        judged_relevant_count=baseline_metrics.judged_relevant_count,
        filtered_pool_candidate_count=len(filtered_pool_product_ids),
        candidate_coverage=coverage,
        baseline=baseline_metrics,
        ltr=ltr_metrics,
        diagnostics=diagnostics,
    )


def _ranked_product_ids_for_pool(
    *,
    query_text: str,
    filtered_candidates: tuple[RetrievalCandidate, ...],
    evaluation_top_k: int,
    product_context_provider: RankingProductContextProvider,
    baseline_config: BaselineRankingConfig,
    artifact: LTRModelArtifact,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    if not filtered_candidates:
        return (), ()
    query = build_query_representation(query_text)
    filtered_response = RetrievalResponse(candidates=filtered_candidates, metadata=None)
    ranking_request = ranking_request_from_retrieval_response(
        query=query,
        response=filtered_response,
        top_k=evaluation_top_k,
    )
    contexts = product_context_provider.load_contexts(
        product_ids=tuple(candidate.product_id for candidate in ranking_request.candidates),
    )
    raw_features = extract_features_for_request(ranking_request, product_context_by_id=contexts)
    normalized = normalize_features_for_query(raw_features)
    feature_map = {row.product_id: row for row in normalized}
    baseline_response = rank_candidates(
        request=ranking_request,
        normalized_features_by_product_id=feature_map,
        baseline_config=baseline_config,
    )
    ltr_response = rank_candidates_with_ltr(
        request=ranking_request,
        normalized_features_by_product_id=feature_map,
        artifact=artifact,
        validate_artifact=False,
    )
    baseline_ids = tuple(row.product_id for row in baseline_response.ranked_candidates)
    ltr_ids = tuple(row.product_id for row in ltr_response.ranked_candidates)
    return baseline_ids, ltr_ids


class LTRBaselineBenchmarkEvaluator:
    """Compare Phase 10.4 baseline vs offline LTR on the lexical benchmark."""

    def __init__(self, config: RankingEvaluationConfig | None = None) -> None:
        self._config = config or RankingEvaluationConfig()

    @property
    def config(self) -> RankingEvaluationConfig:
        return self._config

    def evaluate_from_lists(
        self,
        benchmark: LexicalRetrievalBenchmark,
        *,
        baseline_by_query_id: dict[str, tuple[str, ...]],
        ltr_by_query_id: dict[str, tuple[str, ...]],
        pool_by_query_id: dict[str, tuple[str, ...]],
        artifact: LTRModelArtifact,
    ) -> LTRBaselineBenchmarkEvaluationResult:
        per_query: list[LTRBaselineQueryEvaluationResult] = []
        for evaluation_query in benchmark.queries:
            query_id = evaluation_query.query_id
            row = evaluate_baseline_vs_ltr_query(
                evaluation_query,
                baseline_ranked_product_ids=baseline_by_query_id.get(query_id, ()),
                ltr_ranked_product_ids=ltr_by_query_id.get(query_id, ()),
                filtered_pool_product_ids=pool_by_query_id.get(query_id, ()),
                config=self._config,
            )
            per_query.append(row)
        return self._aggregate(benchmark, per_query, artifact)

    def evaluate_production_pipeline(
        self,
        benchmark: LexicalRetrievalBenchmark,
        pipeline: ProductionRetrievalPipeline,
        artifact: LTRModelArtifact,
    ) -> LTRBaselineBenchmarkEvaluationResult:
        if pipeline.config.candidate_pool_top_k != self._config.candidate_pool_top_k:
            msg = "pipeline candidate_pool_top_k must match RankingEvaluationConfig"
            raise RankingError(msg)
        if pipeline.config.candidate_pool_top_k < self._config.evaluation_top_k:
            msg = "candidate_pool_top_k must be >= evaluation_top_k"
            raise RankingError(msg)
        stage = pipeline.ranking_stage or ProductionRankingStageConfig()
        if not stage.enabled:
            msg = "baseline ranking must be enabled for baseline vs LTR evaluation"
            raise RankingError(msg)
        if pipeline.product_context_provider is None:
            msg = "product_context_provider is required for baseline vs LTR evaluation"
            raise RankingError(msg)

        per_query: list[LTRBaselineQueryEvaluationResult] = []
        for evaluation_query in benchmark.queries:
            eval_request = RetrievalRequest(
                query=build_query_representation(evaluation_query.query_text),
                top_k=self._config.evaluation_top_k,
            )
            bundle = pipeline.retrieve_ranked_evaluation_bundle(eval_request)
            pool_request = RetrievalRequest(
                query=eval_request.query,
                top_k=self._config.candidate_pool_top_k,
            )
            pool_response = pipeline.retrieve(pool_request)
            filtered = pool_response.candidates
            pool_ids = tuple(candidate.product_id for candidate in filtered)
            if pool_ids != bundle.filtered_pool_product_ids:
                msg = "filtered candidate pool must match ranked evaluation bundle pool"
                raise RankingError(msg)
            baseline_ids = tuple(
                row.product_id for row in bundle.ranked_search.ranking.ranked_candidates
            )
            _, ltr_ids = _ranked_product_ids_for_pool(
                query_text=evaluation_query.query_text,
                filtered_candidates=filtered,
                evaluation_top_k=self._config.evaluation_top_k,
                product_context_provider=pipeline.product_context_provider,
                baseline_config=stage.baseline_config,
                artifact=artifact,
            )
            row = evaluate_baseline_vs_ltr_query(
                evaluation_query,
                baseline_ranked_product_ids=baseline_ids,
                ltr_ranked_product_ids=ltr_ids,
                filtered_pool_product_ids=bundle.filtered_pool_product_ids,
                config=self._config,
            )
            per_query.append(row)
        return self._aggregate(benchmark, per_query, artifact)

    def _aggregate(
        self,
        benchmark: LexicalRetrievalBenchmark,
        per_query: list[LTRBaselineQueryEvaluationResult],
        artifact: LTRModelArtifact,
    ) -> LTRBaselineBenchmarkEvaluationResult:
        ordered = tuple(sorted(per_query, key=lambda item: item.query_id))
        baseline_aggregate = aggregate_query_results(
            tuple(row.baseline for row in ordered),
            k_values=self._config.k_values,
        )
        ltr_aggregate = aggregate_query_results(
            tuple(row.ltr for row in ordered),
            k_values=self._config.k_values,
        )
        spec = artifact.metadata.feature_spec
        lineage = LTRBaselineEvaluationLineage(
            benchmark_name=benchmark.benchmark_name,
            benchmark_version=benchmark.benchmark_version,
            evaluation_top_k=self._config.evaluation_top_k,
            candidate_pool_top_k=self._config.candidate_pool_top_k,
            k_values=self._config.k_values,
            baseline_ranking_version=BASELINE_RANKER_VERSION,
            ltr_inference_version=LTR_INFERENCE_VERSION,
            ltr_artifact_version=artifact.metadata.artifact_version,
            ltr_model_version=artifact.metadata.ltr_version,
            feature_schema_version=spec.feature_schema_version,
            normalization_schema_version=spec.normalization_schema_version,
            ltr_feature_order_version=spec.feature_order_version,
            missing_value_policy_version=spec.missing_value_policy_version,
            query_set_version=artifact.metadata.query_set_version,
            judgment_source_version=artifact.metadata.judgment_source_version,
        )
        judged_total = sum(row.judged_relevant_count for row in ordered)
        return LTRBaselineBenchmarkEvaluationResult(
            benchmark_name=benchmark.benchmark_name,
            benchmark_version=benchmark.benchmark_version,
            query_count=len(ordered),
            total_judged_relevance_count=judged_total,
            evaluation_top_k=self._config.evaluation_top_k,
            candidate_pool_top_k=self._config.candidate_pool_top_k,
            k_values=self._config.k_values,
            baseline=baseline_aggregate,
            ltr=ltr_aggregate,
            per_query=ordered,
            comparison=compare_baseline_ltr_metrics(
                baseline=baseline_aggregate,
                ltr=ltr_aggregate,
                k_values=self._config.k_values,
            ),
            lineage=lineage,
        )


__all__ = [
    "LTRBaselineBenchmarkEvaluator",
    "evaluate_baseline_vs_ltr_query",
]
