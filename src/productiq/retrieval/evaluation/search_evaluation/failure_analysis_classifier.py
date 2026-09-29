"""Classify search evaluation failure outcomes from artifact ranks (Phase 12.8)."""

from __future__ import annotations

from collections.abc import Sequence

from productiq.exceptions.base import RetrievalError
from productiq.retrieval.evaluation.search_evaluation.failure_analysis_schema import (
    SearchFailureAnalysisRecord,
    SearchFailureCategory,
)


def build_rank_lookup(
    ranked_product_ids: Sequence[str],
    *,
    source_label: str,
) -> dict[str, int]:
    ranks: dict[str, int] = {}
    for index, product_id in enumerate(ranked_product_ids, start=1):
        if not str(product_id).strip():
            msg = f"empty product_id in {source_label} ranked list"
            raise RetrievalError(msg)
        if product_id in ranks:
            msg = f"duplicate product_id {product_id!r} in {source_label} ranked list"
            raise RetrievalError(msg)
        ranks[product_id] = index
    return ranks


def classify_failure_category(
    *,
    rank: int | None,
    analysis_k: int,
    evaluated_depth: int,
    depth_limited_threshold: int = 10,
) -> SearchFailureCategory:
    if analysis_k <= 0 or evaluated_depth <= 0:
        msg = "analysis_k and evaluated_depth must be positive"
        raise RetrievalError(msg)
    if rank is None:
        return SearchFailureCategory.ABSENT_FROM_EVALUATED_DEPTH
    if rank > evaluated_depth:
        msg = f"rank {rank} exceeds evaluated_depth {evaluated_depth}"
        raise RetrievalError(msg)
    if rank <= analysis_k:
        return SearchFailureCategory.RANKED_IN_TOP_K
    if rank > depth_limited_threshold:
        return SearchFailureCategory.DEPTH_LIMITED
    return SearchFailureCategory.RETRIEVED_BELOW_K


def build_failure_record(
    *,
    query_id: str,
    product_id: str,
    relevance_grade: int,
    variant_name: str,
    variant_version: str,
    analysis_k: int,
    evaluated_depth: int,
    ranked_product_ids: Sequence[str],
    depth_limited_threshold: int = 10,
    reference_rank: int | None = None,
    ranking_rank: int | None = None,
    constraint_incompatible: bool = False,
) -> SearchFailureAnalysisRecord:
    lookup = build_rank_lookup(ranked_product_ids, source_label=variant_name)
    rank = lookup.get(product_id)
    if constraint_incompatible:
        category = SearchFailureCategory.JUDGED_RELEVANT_BUT_CONSTRAINT_INCOMPATIBLE
    else:
        category = classify_failure_category(
            rank=rank,
            analysis_k=analysis_k,
            evaluated_depth=evaluated_depth,
            depth_limited_threshold=depth_limited_threshold,
        )
    effective_rank = ranking_rank if ranking_rank is not None else rank
    rank_delta: int | None = None
    if reference_rank is not None and effective_rank is not None:
        rank_delta = effective_rank - reference_rank
    observations: list[str] = []
    if rank is None:
        observations.append(
            f"product {product_id!r} absent from evaluated top-{evaluated_depth} for variant {variant_name!r}"
        )
    else:
        observations.append(
            f"product {product_id!r} at rank {rank} within evaluated depth {evaluated_depth}"
        )
    if reference_rank is not None and effective_rank is not None:
        observations.append(
            f"rank_delta={rank_delta} (candidate {effective_rank} minus reference {reference_rank})"
        )
    elif reference_rank is not None and effective_rank is None:
        observations.append("candidate rank unknown; rank_delta not computed")
    return SearchFailureAnalysisRecord(
        query_id=query_id,
        product_id=product_id,
        relevance_grade=relevance_grade,
        variant_name=variant_name,
        variant_version=variant_version,
        analysis_k=analysis_k,
        evaluated_depth=evaluated_depth,
        retrieved=rank is not None,
        in_top_k=rank is not None and rank <= analysis_k,
        retrieval_rank=rank,
        ranking_rank=effective_rank,
        reference_rank=reference_rank,
        rank_delta=rank_delta,
        failure_category=category,
        observations=tuple(observations),
    )


def rank_for_product(
    ranked_product_ids: Sequence[str],
    product_id: str,
) -> int | None:
    lookup = build_rank_lookup(ranked_product_ids, source_label="ranked_list")
    return lookup.get(product_id)


def retrieval_pattern_label(
    *,
    bm25_rank: int | None,
    semantic_rank: int | None,
    evaluated_depth: int,
) -> str:
    """Phase 4.18-compatible pattern label from BM25/semantic ranks within evaluated depth."""
    from productiq.retrieval.evaluation.failure_analyzer import (
        derive_retrieval_pattern_classifications,
    )

    patterns = derive_retrieval_pattern_classifications(
        bm25_rank=bm25_rank,
        semantic_rank=semantic_rank,
        rrf_rank=None,
        retrieval_top_k=evaluated_depth,
    )
    if not patterns:
        return "NOT_RETRIEVED_BY_EITHER"
    return patterns[0].value


__all__ = [
    "build_failure_record",
    "build_rank_lookup",
    "classify_failure_category",
    "rank_for_product",
    "retrieval_pattern_label",
]
