"""Retrieval feature projection (Phase 10.2)."""

from __future__ import annotations

from productiq.ranking.feature_schema import RetrievalFeatureGroup
from productiq.retrieval.contracts import RetrievalCandidate, RetrievalMethod


def extract_retrieval_features(candidate: RetrievalCandidate) -> RetrievalFeatureGroup:
    """Project existing retrieval provenance; does not recompute BM25, vector, or RRF."""
    methods = candidate.resolved_retrieval_methods()
    by_bm25 = RetrievalMethod.BM25 in methods
    by_vector = RetrievalMethod.VECTOR in methods

    bm25_score = candidate.bm25_score
    if bm25_score is None and by_bm25 and not by_vector:
        bm25_score = candidate.score

    vector_similarity = candidate.vector_score
    if vector_similarity is None and by_vector and not by_bm25:
        vector_similarity = candidate.score

    return RetrievalFeatureGroup(
        bm25_score=bm25_score,
        bm25_rank=candidate.bm25_rank,
        vector_similarity=vector_similarity,
        vector_rank=candidate.vector_rank,
        rrf_score=candidate.fusion_score,
        retrieved_by_bm25=by_bm25,
        retrieved_by_vector=by_vector,
        retrieved_by_both=by_bm25 and by_vector,
    )


__all__ = ["extract_retrieval_features"]
