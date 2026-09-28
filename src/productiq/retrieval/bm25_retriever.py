"""BM25 candidate retrieval implementing the Phase 4.2 ``Retriever`` protocol (Phase 4.7)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from productiq.retrieval.bm25 import (
    BM25Config,
    BM25Scorer,
    apply_bm25_top_k,
    unique_lexical_query_terms,
)
from productiq.retrieval.contracts import (
    RetrievalCandidate,
    RetrievalMethod,
    RetrievalRequest,
    RetrievalResponse,
    RetrievalResponseMetadata,
    Retriever,
)
from productiq.retrieval.index_builder import load_inverted_lexical_index
from productiq.retrieval.lexical import InvertedLexicalIndex, retrieve_lexical_candidates
from productiq.retrieval.query_for_retrieval import build_retrieval_query_view


@dataclass(frozen=True)
class BM25Retriever:
    """Lexical BM25 retrieval over a persisted or in-memory ``InvertedLexicalIndex``."""

    index: InvertedLexicalIndex
    scorer: BM25Scorer

    def __init__(
        self,
        index: InvertedLexicalIndex,
        *,
        config: BM25Config | None = None,
        scorer: BM25Scorer | None = None,
    ) -> None:
        object.__setattr__(self, "index", index)
        object.__setattr__(self, "scorer", scorer or BM25Scorer(index, config=config))

    def retrieve(self, request: RetrievalRequest) -> RetrievalResponse:
        view = build_retrieval_query_view(request.query)
        lexical_text = view.lexical_retrieval_text
        query_terms = unique_lexical_query_terms(lexical_text)
        response_metadata = RetrievalResponseMetadata(requested_top_k=request.top_k)

        if not query_terms:
            return RetrievalResponse(candidates=(), metadata=response_metadata)

        candidate_product_ids = retrieve_lexical_candidates(self.index, lexical_text)
        if not candidate_product_ids:
            return RetrievalResponse(candidates=(), metadata=response_metadata)

        scored = self.scorer.score_lexical_query(
            lexical_text,
            candidate_product_ids=candidate_product_ids,
        )
        ranked = apply_bm25_top_k(scored, request.top_k)
        candidates = tuple(
            RetrievalCandidate(
                product_id=scored_candidate.product_id,
                score=scored_candidate.score,
                method=RetrievalMethod.BM25,
            )
            for scored_candidate in ranked
        )
        return RetrievalResponse(candidates=candidates, metadata=response_metadata)


def create_bm25_retriever(
    index: InvertedLexicalIndex,
    *,
    config: BM25Config | None = None,
) -> BM25Retriever:
    """Construct a ``BM25Retriever`` from a loaded inverted lexical index."""
    return BM25Retriever(index, config=config)


def create_bm25_retriever_from_index_path(
    index_path: Path,
    *,
    config: BM25Config | None = None,
) -> BM25Retriever:
    """Load a persisted index artifact and construct a ``BM25Retriever``."""
    return BM25Retriever(load_inverted_lexical_index(index_path), config=config)


def bm25_retriever_satisfies_protocol(retriever: BM25Retriever) -> bool:
    """Return whether ``retriever`` implements the ``Retriever`` protocol."""
    return isinstance(retriever, Retriever)


__all__ = [
    "BM25Retriever",
    "bm25_retriever_satisfies_protocol",
    "create_bm25_retriever",
    "create_bm25_retriever_from_index_path",
]
