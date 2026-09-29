"""Ranking variant executors for fixed-candidate search evaluation (Phase 12.7)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from pydantic import ValidationError

from productiq.exceptions.base import RankingError, RetrievalError
from productiq.ranking.adapters import ranking_request_from_retrieval_response
from productiq.ranking.baseline_config import BASELINE_RANKER_VERSION, BaselineRankingConfig
from productiq.ranking.baseline_ranker import rank_candidates
from productiq.ranking.contracts import RankingRequest, RankingResponse
from productiq.ranking.feature_extractor import extract_features_for_request
from productiq.ranking.ltr.artifact import LTRModelArtifact
from productiq.ranking.ltr.inference import rank_candidates_with_ltr
from productiq.ranking.ltr.inference_config import LTR_INFERENCE_VERSION
from productiq.ranking.normalization import normalize_features_for_query
from productiq.ranking.product_context_provider import RankingProductContextProvider
from productiq.representation.query_contract import build_query_representation
from productiq.retrieval.contracts import RetrievalResponse
from productiq.retrieval.evaluation.search_evaluation.benchmark_schema import SearchEvaluationQuery
from productiq.retrieval.evaluation.search_evaluation.metrics import (
    validate_search_ranked_product_ids,
)
from productiq.retrieval.evaluation.search_evaluation.ranking_experiment_schema import (
    SearchQueryCandidateSet,
    SearchRankingVariantType,
)
from productiq.retrieval.evaluation.search_evaluation.request_schema import (
    SearchRankedResultsForQuery,
)
from productiq.retrieval.evaluation.search_evaluation.run_context import SearchEvaluationRunContext


@dataclass(frozen=True, slots=True)
class SearchRankingExecutionContext:
    """Phase 10 dependencies for ranking variants (no retrieval execution)."""

    ranking_top_k: int
    product_context_provider: RankingProductContextProvider
    baseline_config: BaselineRankingConfig
    ltr_artifact: LTRModelArtifact | None = None


class RankingVariantExecutor(Protocol):
    """Rank a fixed candidate set for one benchmark query."""

    def execute_query(
        self,
        query: SearchEvaluationQuery,
        candidate_set: SearchQueryCandidateSet,
        context: SearchRankingExecutionContext,
    ) -> SearchRankedResultsForQuery: ...


def _require_candidate_set(
    query: SearchEvaluationQuery,
    candidate_set: SearchQueryCandidateSet,
) -> tuple[RetrievalResponse, tuple[str, ...]]:
    if candidate_set.query_id != query.query_id:
        msg = (
            f"candidate_set query_id {candidate_set.query_id!r} "
            f"does not match benchmark query {query.query_id!r}"
        )
        raise RetrievalError(msg)
    if not candidate_set.candidates:
        msg = (
            f"candidate_set for query {query.query_id!r} missing retrieval candidates; "
            "ranking variants require full RetrievalCandidate rows"
        )
        raise RetrievalError(msg)
    product_ids = candidate_set.candidate_product_ids
    return (
        RetrievalResponse(candidates=candidate_set.candidates, metadata=None),
        product_ids,
    )


def _ranked_ids_from_response(
    query: SearchEvaluationQuery,
    response: RankingResponse,
    *,
    ranking_top_k: int,
) -> SearchRankedResultsForQuery:
    ranked = validate_search_ranked_product_ids(
        tuple(row.product_id for row in response.ranked_candidates[:ranking_top_k])
    )
    return SearchRankedResultsForQuery(query_id=query.query_id, ranked_product_ids=ranked)


@dataclass(frozen=True, slots=True)
class RetrievalOrderRankingExecutor:
    """Preserve fixed candidate retrieval order as the ranked list."""

    def execute_query(
        self,
        query: SearchEvaluationQuery,
        candidate_set: SearchQueryCandidateSet,
        context: SearchRankingExecutionContext,
    ) -> SearchRankedResultsForQuery:
        _response, product_ids = _require_candidate_set(query, candidate_set)
        ranked = validate_search_ranked_product_ids(product_ids[: context.ranking_top_k])
        return SearchRankedResultsForQuery(query_id=query.query_id, ranked_product_ids=ranked)


@dataclass(frozen=True, slots=True)
class BaselineRankerRankingExecutor:
    """Phase 10.4 deterministic baseline ranker over the fixed pool."""

    def execute_query(
        self,
        query: SearchEvaluationQuery,
        candidate_set: SearchQueryCandidateSet,
        context: SearchRankingExecutionContext,
    ) -> SearchRankedResultsForQuery:
        pool_response, _ = _require_candidate_set(query, candidate_set)
        ranking_request = ranking_request_from_retrieval_response(
            query=build_query_representation(query.query_text),
            response=pool_response,
            top_k=context.ranking_top_k,
        )
        response = _rank_with_baseline(ranking_request, context)
        return _ranked_ids_from_response(query, response, ranking_top_k=context.ranking_top_k)


@dataclass(frozen=True, slots=True)
class LtrRankingExecutor:
    """Phase 10.8 experimental LTR inference over the fixed pool."""

    def execute_query(
        self,
        query: SearchEvaluationQuery,
        candidate_set: SearchQueryCandidateSet,
        context: SearchRankingExecutionContext,
    ) -> SearchRankedResultsForQuery:
        if context.ltr_artifact is None:
            msg = "LTR ranking variant requires a loaded LTRModelArtifact"
            raise RetrievalError(msg)
        pool_response, _ = _require_candidate_set(query, candidate_set)
        ranking_request = ranking_request_from_retrieval_response(
            query=build_query_representation(query.query_text),
            response=pool_response,
            top_k=context.ranking_top_k,
        )
        response = _rank_with_ltr(ranking_request, context)
        return _ranked_ids_from_response(query, response, ranking_top_k=context.ranking_top_k)


def _rank_with_baseline(
    ranking_request: RankingRequest,
    context: SearchRankingExecutionContext,
) -> RankingResponse:
    try:
        contexts = context.product_context_provider.load_contexts(
            product_ids=tuple(candidate.product_id for candidate in ranking_request.candidates),
        )
        raw_features = extract_features_for_request(ranking_request, product_context_by_id=contexts)
        normalized = normalize_features_for_query(raw_features)
        feature_map = {row.product_id: row for row in normalized}
        return rank_candidates(
            request=ranking_request,
            normalized_features_by_product_id=feature_map,
            baseline_config=context.baseline_config,
        )
    except RankingError:
        raise
    except ValidationError as exc:
        msg = f"baseline ranking failed: {exc}"
        raise RetrievalError(msg) from exc


def _rank_with_ltr(
    ranking_request: RankingRequest,
    context: SearchRankingExecutionContext,
) -> RankingResponse:
    artifact = context.ltr_artifact
    if artifact is None:
        msg = "LTR artifact missing"
        raise RetrievalError(msg)
    try:
        contexts = context.product_context_provider.load_contexts(
            product_ids=tuple(candidate.product_id for candidate in ranking_request.candidates),
        )
        raw_features = extract_features_for_request(ranking_request, product_context_by_id=contexts)
        normalized = normalize_features_for_query(raw_features)
        feature_map = {row.product_id: row for row in normalized}
        return rank_candidates_with_ltr(
            request=ranking_request,
            normalized_features_by_product_id=feature_map,
            artifact=artifact,
            validate_artifact=False,
        )
    except RankingError:
        raise
    except ValidationError as exc:
        msg = f"LTR ranking failed: {exc}"
        raise RetrievalError(msg) from exc


def ranking_executor_for_variant_type(
    variant_type: SearchRankingVariantType,
) -> RankingVariantExecutor:
    if variant_type is SearchRankingVariantType.RETRIEVAL_ORDER:
        return RetrievalOrderRankingExecutor()
    if variant_type is SearchRankingVariantType.BASELINE_RANKER:
        return BaselineRankerRankingExecutor()
    if variant_type is SearchRankingVariantType.LTR:
        return LtrRankingExecutor()
    msg = f"unsupported ranking variant type {variant_type!r}"
    raise RetrievalError(msg)


@dataclass(frozen=True, slots=True)
class FixedCandidateRankingSearchExecutor:
    """Adapt a ranking variant executor to the Phase 12.4 search evaluation protocol."""

    ranking_executor: RankingVariantExecutor
    candidate_sets_by_query_id: dict[str, SearchQueryCandidateSet]
    ranking_context: SearchRankingExecutionContext

    def execute_query(
        self,
        query: SearchEvaluationQuery,
        context: SearchEvaluationRunContext,
    ) -> SearchRankedResultsForQuery:
        del context
        candidate_set = self.candidate_sets_by_query_id.get(query.query_id)
        if candidate_set is None:
            msg = f"missing fixed candidate set for query {query.query_id!r}"
            raise RetrievalError(msg)
        try:
            return self.ranking_executor.execute_query(query, candidate_set, self.ranking_context)
        except RankingError as exc:
            msg = f"ranking variant failed for query {query.query_id!r}: {exc}"
            raise RetrievalError(msg) from exc


def default_ranking_lineage_labels(variant_type: SearchRankingVariantType) -> tuple[str, ...]:
    if variant_type is SearchRankingVariantType.RETRIEVAL_ORDER:
        return ("ranking:retrieval_order",)
    if variant_type is SearchRankingVariantType.BASELINE_RANKER:
        return ("ranking:baseline_ranker", BASELINE_RANKER_VERSION)
    return ("ranking:ltr", LTR_INFERENCE_VERSION)


__all__ = [
    "BaselineRankerRankingExecutor",
    "FixedCandidateRankingSearchExecutor",
    "LtrRankingExecutor",
    "RankingVariantExecutor",
    "RetrievalOrderRankingExecutor",
    "SearchRankingExecutionContext",
    "default_ranking_lineage_labels",
    "ranking_executor_for_variant_type",
]
