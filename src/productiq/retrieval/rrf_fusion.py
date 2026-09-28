"""Reciprocal Rank Fusion (Phase 4.16)."""

from __future__ import annotations

from dataclasses import dataclass

from productiq.retrieval.contracts import (
    RetrievalCandidate,
    RetrievalMethod,
    RetrievalResponse,
    RetrievalResponseMetadata,
)
from productiq.retrieval.exceptions import RetrievalError
from productiq.retrieval.hybrid import union_lexical_and_semantic_candidates
from productiq.retrieval.rrf_config import RRFConfig


def rrf_contribution(*, rank: int, rank_constant: int) -> float:
    """Single reciprocal-rank term ``1 / (k + rank)`` with 1-based ``rank``."""
    if rank <= 0:
        msg = "RRF rank must be a positive 1-based integer"
        raise ValueError(msg)
    if rank_constant <= 0:
        msg = "RRF rank_constant must be positive"
        raise ValueError(msg)
    return 1.0 / (rank_constant + rank)


def compute_rrf_score(
    *,
    bm25_rank: int | None,
    vector_rank: int | None,
    rank_constant: int,
) -> float:
    score = 0.0
    if bm25_rank is not None:
        score += rrf_contribution(rank=bm25_rank, rank_constant=rank_constant)
    if vector_rank is not None:
        score += rrf_contribution(rank=vector_rank, rank_constant=rank_constant)
    return score


@dataclass(frozen=True)
class SourceRankEntry:
    rank: int
    native_score: float


def _ranked_entries_from_response(
    response: RetrievalResponse,
    *,
    expected_method: RetrievalMethod,
    source_label: str,
) -> dict[str, SourceRankEntry]:
    entries: dict[str, SourceRankEntry] = {}
    for index, candidate in enumerate(response.candidates):
        if candidate.method is not expected_method:
            msg = f"{source_label} fusion input must contain {expected_method.value} candidates"
            raise ValueError(msg)
        product_id = candidate.product_id
        if product_id in entries:
            msg = (
                f"duplicate product_id={product_id} in {source_label} retrieval list; "
                "RRF requires unique ranked lists"
            )
            raise RetrievalError(msg)
        entries[product_id] = SourceRankEntry(rank=index + 1, native_score=candidate.score)
    return entries


def _provenance_methods(
    *,
    bm25_rank: int | None,
    vector_rank: int | None,
) -> tuple[RetrievalMethod, ...]:
    methods: list[RetrievalMethod] = []
    if bm25_rank is not None:
        methods.append(RetrievalMethod.BM25)
    if vector_rank is not None:
        methods.append(RetrievalMethod.VECTOR)
    return tuple(methods)


def fused_candidate_from_rrf(
    product_id: str,
    *,
    fusion_score: float,
    bm25_rank: int | None,
    vector_rank: int | None,
    bm25_score: float | None,
    vector_score: float | None,
) -> RetrievalCandidate:
    methods = _provenance_methods(bm25_rank=bm25_rank, vector_rank=vector_rank)
    if not methods:
        msg = "fused candidate requires at least one source rank"
        raise ValueError(msg)
    return RetrievalCandidate(
        product_id=product_id,
        score=fusion_score,
        fusion_score=fusion_score,
        method=RetrievalMethod.HYBRID,
        retrieval_methods=methods,
        bm25_score=bm25_score,
        vector_score=vector_score,
        bm25_rank=bm25_rank,
        vector_rank=vector_rank,
    )


@dataclass(frozen=True)
class RRFFusionStatistics:
    lexical_candidate_count: int
    semantic_candidate_count: int
    hybrid_pool_count: int
    overlap_count: int
    fused_candidate_count: int
    rank_constant: int


def fuse_lexical_and_semantic_responses(
    lexical_response: RetrievalResponse,
    semantic_response: RetrievalResponse,
    *,
    config: RRFConfig,
    output_top_k: int,
) -> tuple[tuple[RetrievalCandidate, ...], RRFFusionStatistics]:
    """Fuse BM25 and semantic ranked lists with RRF; truncate after ranking."""
    if output_top_k <= 0:
        msg = "output_top_k must be positive"
        raise ValueError(msg)
    bm25_entries = _ranked_entries_from_response(
        lexical_response,
        expected_method=RetrievalMethod.BM25,
        source_label="lexical",
    )
    vector_entries = _ranked_entries_from_response(
        semantic_response,
        expected_method=RetrievalMethod.VECTOR,
        source_label="semantic",
    )
    _, pool_stats = union_lexical_and_semantic_candidates(
        lexical_response,
        semantic_response,
        requested_top_k=output_top_k,
    )
    product_ids = set(bm25_entries) | set(vector_entries)
    scored: list[tuple[str, float, int | None, int | None, float | None, float | None]] = []
    for product_id in product_ids:
        bm25 = bm25_entries.get(product_id)
        vector = vector_entries.get(product_id)
        bm25_rank = bm25.rank if bm25 else None
        vector_rank = vector.rank if vector else None
        fusion = compute_rrf_score(
            bm25_rank=bm25_rank,
            vector_rank=vector_rank,
            rank_constant=config.rank_constant,
        )
        scored.append(
            (
                product_id,
                fusion,
                bm25_rank,
                vector_rank,
                bm25.native_score if bm25 else None,
                vector.native_score if vector else None,
            )
        )
    scored.sort(key=lambda row: (-row[1], row[0]))
    truncated = scored[:output_top_k]
    candidates = tuple(
        fused_candidate_from_rrf(
            product_id,
            fusion_score=fusion,
            bm25_rank=bm25_rank,
            vector_rank=vector_rank,
            bm25_score=bm25_score,
            vector_score=vector_score,
        )
        for product_id, fusion, bm25_rank, vector_rank, bm25_score, vector_score in truncated
    )
    stats = RRFFusionStatistics(
        lexical_candidate_count=len(lexical_response.candidates),
        semantic_candidate_count=len(semantic_response.candidates),
        hybrid_pool_count=len(product_ids),
        overlap_count=pool_stats.overlap_count,
        fused_candidate_count=len(candidates),
        rank_constant=config.rank_constant,
    )
    return candidates, stats


def build_rrf_fused_retrieval_response(
    lexical_response: RetrievalResponse,
    semantic_response: RetrievalResponse,
    *,
    config: RRFConfig,
    requested_top_k: int,
) -> RetrievalResponse:
    candidates, stats = fuse_lexical_and_semantic_responses(
        lexical_response,
        semantic_response,
        config=config,
        output_top_k=requested_top_k,
    )
    return RetrievalResponse(
        candidates=candidates,
        metadata=RetrievalResponseMetadata(
            requested_top_k=requested_top_k,
            lexical_candidate_count=stats.lexical_candidate_count,
            semantic_candidate_count=stats.semantic_candidate_count,
            unique_candidate_count=stats.hybrid_pool_count,
            overlap_count=stats.overlap_count,
            hybrid_pool_count=stats.hybrid_pool_count,
            fused_candidate_count=stats.fused_candidate_count,
            rrf_rank_constant=stats.rank_constant,
        ),
    )


__all__ = [
    "RRFFusionStatistics",
    "SourceRankEntry",
    "build_rrf_fused_retrieval_response",
    "compute_rrf_score",
    "fuse_lexical_and_semantic_responses",
    "fused_candidate_from_rrf",
    "rrf_contribution",
]
