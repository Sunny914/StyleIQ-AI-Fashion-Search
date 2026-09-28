"""Map retrieval outputs into ranking contracts (Phase 10.1)."""

from __future__ import annotations

from productiq.ranking.config import RankingConfig
from productiq.ranking.contracts import RankingCandidate, RankingRequest
from productiq.representation.query_contract import QueryRepresentation
from productiq.retrieval.contracts import RetrievalCandidate, RetrievalResponse


def ranking_candidate_from_retrieval(candidate: RetrievalCandidate) -> RankingCandidate:
    """Project one retrieval candidate into the ranking input contract."""
    return RankingCandidate(product_id=candidate.product_id, retrieval=candidate)


def ranking_candidates_from_retrieval_response(
    response: RetrievalResponse,
) -> tuple[RankingCandidate, ...]:
    """Preserve retrieval order when building ranking inputs."""
    return tuple(ranking_candidate_from_retrieval(row) for row in response.candidates)


def ranking_request_from_retrieval_response(
    *,
    query: QueryRepresentation,
    response: RetrievalResponse,
    top_k: int,
    config: RankingConfig | None = None,
) -> RankingRequest:
    """Build a ranking request from production retrieval output without retrieval side effects."""
    return RankingRequest(
        query=query,
        candidates=ranking_candidates_from_retrieval_response(response),
        top_k=top_k,
        config=config or RankingConfig(),
    )


__all__ = [
    "ranking_candidate_from_retrieval",
    "ranking_candidates_from_retrieval_response",
    "ranking_request_from_retrieval_response",
]
