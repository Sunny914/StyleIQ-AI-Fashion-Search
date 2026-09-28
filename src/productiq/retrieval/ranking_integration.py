"""Baseline ranking stage orchestration for production search (Phase 10.5)."""

from __future__ import annotations

import math
import time
from dataclasses import dataclass

from productiq.ranking.adapters import (
    ranking_candidates_from_retrieval_response,
    ranking_request_from_retrieval_response,
)
from productiq.ranking.baseline_config import BaselineRankingConfig
from productiq.ranking.baseline_ranker import rank_candidates
from productiq.ranking.config import RankingConfig
from productiq.ranking.contracts import RankedCandidate, RankingResponse
from productiq.ranking.feature_extractor import extract_features_for_request
from productiq.ranking.normalization import normalize_features_for_query
from productiq.ranking.product_context_provider import RankingProductContextProvider
from productiq.representation.query_contract import QueryRepresentation
from productiq.retrieval.contracts import RetrievalCandidate, RetrievalResponse
from productiq.retrieval.production_ranking_config import RETRIEVAL_ORDER_RANKING_VERSION
from productiq.retrieval.ranked_search import RankedSearchTimingsMs


@dataclass(frozen=True)
class BaselineRankingStageResult:
    response: RankingResponse
    timings_ms: RankedSearchTimingsMs


def run_baseline_ranking_stage(
    *,
    query: QueryRepresentation,
    filtered_candidates: tuple[RetrievalCandidate, ...],
    top_k: int,
    product_context_provider: RankingProductContextProvider,
    baseline_config: BaselineRankingConfig,
) -> BaselineRankingStageResult:
    """Feature extraction → normalization → baseline ranker over the filtered pool."""
    filtered_response = RetrievalResponse(candidates=filtered_candidates, metadata=None)
    ranking_request = ranking_request_from_retrieval_response(
        query=query,
        response=filtered_response,
        top_k=top_k,
    )
    feature_start = time.perf_counter()
    contexts = product_context_provider.load_contexts(
        product_ids=tuple(candidate.product_id for candidate in ranking_request.candidates),
    )
    raw_features = extract_features_for_request(ranking_request, product_context_by_id=contexts)
    feature_ms = (time.perf_counter() - feature_start) * 1000.0

    normalization_start = time.perf_counter()
    normalized = normalize_features_for_query(raw_features)
    normalization_ms = (time.perf_counter() - normalization_start) * 1000.0

    ranking_start = time.perf_counter()
    feature_map = {row.product_id: row for row in normalized}
    response = rank_candidates(
        request=ranking_request,
        normalized_features_by_product_id=feature_map,
        baseline_config=baseline_config,
    )
    ranking_ms = (time.perf_counter() - ranking_start) * 1000.0
    return BaselineRankingStageResult(
        response=response,
        timings_ms=RankedSearchTimingsMs(
            feature_extraction_ms=feature_ms,
            normalization_ms=normalization_ms,
            ranking_ms=ranking_ms,
        ),
    )


def retrieval_order_ranking_response(
    *,
    query: QueryRepresentation,
    filtered_candidates: tuple[RetrievalCandidate, ...],
    top_k: int,
) -> RankingResponse:
    """Compatibility ranking output preserving filtered retrieval order (baseline disabled)."""
    del query
    filtered_response = RetrievalResponse(candidates=filtered_candidates, metadata=None)
    ranking_candidates = ranking_candidates_from_retrieval_response(filtered_response)
    ranked: list[RankedCandidate] = []
    for index, candidate in enumerate(ranking_candidates[:top_k], start=1):
        retrieval = candidate.retrieval
        score = retrieval.fusion_score if retrieval.fusion_score is not None else retrieval.score
        if not math.isfinite(score):
            msg = "retrieval score must be finite for retrieval-order ranking passthrough"
            raise ValueError(msg)
        ranked.append(
            RankedCandidate(
                product_id=candidate.product_id,
                rank=index,
                ranking_score=score,
                candidate=candidate,
            )
        )
    return RankingResponse(
        ranked_candidates=tuple(ranked),
        requested_top_k=top_k,
        config=RankingConfig(ranking_version=RETRIEVAL_ORDER_RANKING_VERSION),
    )


__all__ = [
    "BaselineRankingStageResult",
    "retrieval_order_ranking_response",
    "run_baseline_ranking_stage",
]
