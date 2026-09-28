"""Hybrid candidate union for Phase 4.15 (no score fusion)."""

from __future__ import annotations

from dataclasses import dataclass

from productiq.retrieval.contracts import (
    RetrievalCandidate,
    RetrievalMethod,
    RetrievalResponse,
    RetrievalResponseMetadata,
)


def _provenance_methods(
    *,
    bm25_score: float | None,
    vector_score: float | None,
) -> tuple[RetrievalMethod, ...]:
    methods: list[RetrievalMethod] = []
    if bm25_score is not None:
        methods.append(RetrievalMethod.BM25)
    if vector_score is not None:
        methods.append(RetrievalMethod.VECTOR)
    return tuple(methods)


def hybrid_candidate_from_native_scores(
    product_id: str,
    *,
    bm25_score: float | None,
    vector_score: float | None,
) -> RetrievalCandidate:
    """Build a hybrid ``RetrievalCandidate`` preserving native scores separately."""
    methods = _provenance_methods(bm25_score=bm25_score, vector_score=vector_score)
    if not methods:
        msg = "hybrid candidate requires at least one native score"
        raise ValueError(msg)
    if bm25_score is not None and vector_score is not None:
        score = 0.0
    elif bm25_score is not None:
        score = bm25_score
    else:
        assert vector_score is not None
        score = vector_score
    return RetrievalCandidate(
        product_id=product_id,
        score=score,
        method=RetrievalMethod.HYBRID,
        retrieval_methods=methods,
        bm25_score=bm25_score,
        vector_score=vector_score,
    )


@dataclass(frozen=True)
class HybridUnionStatistics:
    lexical_candidate_count: int
    semantic_candidate_count: int
    unique_candidate_count: int
    overlap_count: int


@dataclass
class _HybridAccumulator:
    bm25_score: float | None = None
    vector_score: float | None = None


def union_lexical_and_semantic_candidates(
    lexical_response: RetrievalResponse,
    semantic_response: RetrievalResponse,
    *,
    requested_top_k: int,
) -> tuple[tuple[RetrievalCandidate, ...], HybridUnionStatistics]:
    """Union BM25 and semantic candidates by ``product_id`` without score fusion."""
    accumulators: dict[str, _HybridAccumulator] = {}
    lexical_order: list[str] = []
    vector_only_order: list[str] = []

    for candidate in lexical_response.candidates:
        if candidate.method is not RetrievalMethod.BM25:
            msg = "lexical hybrid input must contain BM25 candidates"
            raise ValueError(msg)
        entry = accumulators.get(candidate.product_id)
        if entry is None:
            entry = _HybridAccumulator()
            accumulators[candidate.product_id] = entry
            lexical_order.append(candidate.product_id)
        if entry.bm25_score is None:
            entry.bm25_score = candidate.score
        elif entry.bm25_score != candidate.score:
            msg = f"conflicting BM25 scores for product_id={candidate.product_id}"
            raise ValueError(msg)

    for candidate in semantic_response.candidates:
        if candidate.method is not RetrievalMethod.VECTOR:
            msg = "semantic hybrid input must contain VECTOR candidates"
            raise ValueError(msg)
        entry = accumulators.get(candidate.product_id)
        if entry is None:
            entry = _HybridAccumulator()
            accumulators[candidate.product_id] = entry
            vector_only_order.append(candidate.product_id)
        if entry.vector_score is None:
            entry.vector_score = candidate.score
        elif entry.vector_score != candidate.score:
            msg = f"conflicting vector scores for product_id={candidate.product_id}"
            raise ValueError(msg)

    ordered_product_ids: list[str] = []
    seen: set[str] = set()
    for product_id in lexical_order:
        if product_id in seen:
            continue
        seen.add(product_id)
        ordered_product_ids.append(product_id)
    for product_id in vector_only_order:
        if product_id in seen:
            continue
        seen.add(product_id)
        ordered_product_ids.append(product_id)

    candidates = tuple(
        hybrid_candidate_from_native_scores(
            product_id,
            bm25_score=accumulators[product_id].bm25_score,
            vector_score=accumulators[product_id].vector_score,
        )
        for product_id in ordered_product_ids
    )
    overlap = sum(
        1
        for product_id in ordered_product_ids
        if accumulators[product_id].bm25_score is not None
        and accumulators[product_id].vector_score is not None
    )
    stats = HybridUnionStatistics(
        lexical_candidate_count=len(lexical_response.candidates),
        semantic_candidate_count=len(semantic_response.candidates),
        unique_candidate_count=len(candidates),
        overlap_count=overlap,
    )
    _ = requested_top_k  # preserved in response metadata by caller; union is not truncated to K
    return candidates, stats


def build_hybrid_retrieval_response(
    lexical_response: RetrievalResponse,
    semantic_response: RetrievalResponse,
    *,
    requested_top_k: int,
) -> RetrievalResponse:
    """Assemble a hybrid ``RetrievalResponse`` from lexical and semantic retriever outputs."""
    candidates, stats = union_lexical_and_semantic_candidates(
        lexical_response,
        semantic_response,
        requested_top_k=requested_top_k,
    )
    return RetrievalResponse(
        candidates=candidates,
        metadata=RetrievalResponseMetadata(
            requested_top_k=requested_top_k,
            lexical_candidate_count=stats.lexical_candidate_count,
            semantic_candidate_count=stats.semantic_candidate_count,
            unique_candidate_count=stats.unique_candidate_count,
            overlap_count=stats.overlap_count,
        ),
    )


__all__ = [
    "HybridUnionStatistics",
    "build_hybrid_retrieval_response",
    "hybrid_candidate_from_native_scores",
    "union_lexical_and_semantic_candidates",
]
