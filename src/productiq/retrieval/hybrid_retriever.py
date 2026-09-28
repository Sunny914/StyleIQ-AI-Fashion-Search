"""Hybrid candidate retrieval implementing the Phase 4.2 ``Retriever`` protocol (Phase 4.15)."""

from __future__ import annotations

from dataclasses import dataclass

from productiq.retrieval.contracts import RetrievalRequest, RetrievalResponse, Retriever
from productiq.retrieval.hybrid import build_hybrid_retrieval_response


@dataclass(frozen=True)
class HybridRetriever:
    """Union BM25 and semantic candidate pools with deduplication and provenance."""

    lexical_retriever: Retriever
    semantic_retriever: Retriever

    def retrieve(self, request: RetrievalRequest) -> RetrievalResponse:
        lexical_response = self.lexical_retriever.retrieve(request)
        semantic_response = self.semantic_retriever.retrieve(request)
        return build_hybrid_retrieval_response(
            lexical_response,
            semantic_response,
            requested_top_k=request.top_k,
        )


def create_hybrid_retriever(
    lexical_retriever: Retriever,
    semantic_retriever: Retriever,
) -> HybridRetriever:
    """Construct a hybrid retriever from injected lexical and semantic retrievers."""
    return HybridRetriever(
        lexical_retriever=lexical_retriever,
        semantic_retriever=semantic_retriever,
    )


def hybrid_retriever_satisfies_protocol(retriever: HybridRetriever) -> bool:
    """Return whether ``retriever`` implements the ``Retriever`` protocol."""
    return isinstance(retriever, Retriever)


__all__ = [
    "HybridRetriever",
    "create_hybrid_retriever",
    "hybrid_retriever_satisfies_protocol",
]
