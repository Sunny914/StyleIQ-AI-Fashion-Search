"""RRF hybrid retrieval implementing the Phase 4.2 ``Retriever`` protocol (Phase 4.16)."""

from __future__ import annotations

from dataclasses import dataclass

from productiq.retrieval.contracts import RetrievalRequest, RetrievalResponse, Retriever
from productiq.retrieval.rrf_config import DEFAULT_RRF_RANK_CONSTANT, RRFConfig
from productiq.retrieval.rrf_fusion import build_rrf_fused_retrieval_response


@dataclass(frozen=True)
class RRFHybridRetriever:
    """Fuse BM25 and semantic ranked candidate lists with Reciprocal Rank Fusion."""

    lexical_retriever: Retriever
    semantic_retriever: Retriever
    config: RRFConfig

    def retrieve(self, request: RetrievalRequest) -> RetrievalResponse:
        lexical_response = self.lexical_retriever.retrieve(request)
        semantic_response = self.semantic_retriever.retrieve(request)
        return build_rrf_fused_retrieval_response(
            lexical_response,
            semantic_response,
            config=self.config,
            requested_top_k=request.top_k,
        )


def create_rrf_hybrid_retriever(
    lexical_retriever: Retriever,
    semantic_retriever: Retriever,
    *,
    config: RRFConfig | None = None,
) -> RRFHybridRetriever:
    """Construct an RRF hybrid retriever from injected retrievers."""
    return RRFHybridRetriever(
        lexical_retriever=lexical_retriever,
        semantic_retriever=semantic_retriever,
        config=config or RRFConfig(rank_constant=DEFAULT_RRF_RANK_CONSTANT),
    )


def rrf_hybrid_retriever_satisfies_protocol(retriever: RRFHybridRetriever) -> bool:
    return isinstance(retriever, Retriever)


__all__ = [
    "RRFHybridRetriever",
    "create_rrf_hybrid_retriever",
    "rrf_hybrid_retriever_satisfies_protocol",
]
