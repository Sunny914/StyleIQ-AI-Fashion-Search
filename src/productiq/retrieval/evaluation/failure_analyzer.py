"""Deterministic retrieval failure analysis (Phase 4.17)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from productiq.retrieval.evaluation.failure_analysis_schema import (
    RELEVANCE_JUDGMENT_JUDGED_RELEVANT,
    REPRESENTATION_EVIDENCE_FIELD_NAMES,
    Bm25ObservedClassification,
    FailureAnalysisLineage,
    MethodRetrievalSnapshot,
    ProductRepresentationEvidence,
    QueryProductDiagnosticRecord,
    RetrievalDepthSnapshot,
    RetrievalFailureAnalysisReport,
    RetrievalPatternClassification,
    RrfRetrievalSnapshot,
    SemanticObservedClassification,
)
from productiq.retrieval.evaluation.metrics import validate_positive_k
from productiq.retrieval.rrf_fusion import compute_rrf_score


@dataclass(frozen=True)
class QueryRetrievalArtifactSlice:
    """Normalized per-query retrieval lists from benchmark run artifacts."""

    query_id: str
    query_text: str
    category: str
    judged_relevant_product_ids: tuple[str, ...]
    bm25_retrieved_product_ids: tuple[str, ...]
    semantic_retrieved_product_ids: tuple[str, ...]
    rrf_retrieved_product_ids: tuple[str, ...]
    semantic_native_scores: Mapping[str, float]


def build_rank_lookup(
    retrieved_product_ids: Sequence[str],
    *,
    source_label: str,
) -> dict[str, int]:
    ranks: dict[str, int] = {}
    for index, product_id in enumerate(retrieved_product_ids, start=1):
        if product_id in ranks:
            msg = f"duplicate product_id {product_id!r} in {source_label} retrieved list"
            raise ValueError(msg)
        ranks[product_id] = index
    return ranks


def depth_snapshot(rank: int | None, *, retrieval_top_k: int) -> RetrievalDepthSnapshot:
    validate_positive_k(retrieval_top_k)
    thresholds = (1, 5, 10, 20, 50)
    within = {k: rank is not None and rank <= min(k, retrieval_top_k) for k in thresholds}
    return RetrievalDepthSnapshot(
        at_1=within[1],
        at_5=within[5],
        at_10=within[10],
        at_20=within[20],
        at_50=within[50],
    )


def _method_snapshot(
    *,
    rank: int | None,
    native_score: float | None,
    retrieval_top_k: int,
) -> MethodRetrievalSnapshot:
    return MethodRetrievalSnapshot(
        retrieved=rank is not None,
        rank=rank,
        native_score=native_score,
        depth=depth_snapshot(rank, retrieval_top_k=retrieval_top_k),
    )


def derive_retrieval_pattern_classifications(
    *,
    bm25_rank: int | None,
    semantic_rank: int | None,
    rrf_rank: int | None,
    retrieval_top_k: int,
) -> tuple[RetrievalPatternClassification, ...]:
    in_bm25 = bm25_rank is not None and bm25_rank <= retrieval_top_k
    in_semantic = semantic_rank is not None and semantic_rank <= retrieval_top_k
    patterns: list[RetrievalPatternClassification] = []

    if in_bm25 and in_semantic:
        patterns.append(RetrievalPatternClassification.RETRIEVED_BY_BOTH)
    elif in_bm25:
        patterns.append(RetrievalPatternClassification.BM25_ONLY)
    elif in_semantic:
        patterns.append(RetrievalPatternClassification.SEMANTIC_ONLY)
    else:
        patterns.append(RetrievalPatternClassification.NOT_RETRIEVED_BY_EITHER)

    if (in_bm25 or in_semantic) and rrf_rank is not None:
        worse_than_bm25 = in_bm25 and rrf_rank > bm25_rank  # type: ignore[operator]
        worse_than_semantic = in_semantic and rrf_rank > semantic_rank  # type: ignore[operator]
        if worse_than_bm25 or worse_than_semantic:
            patterns.append(RetrievalPatternClassification.RETRIEVED_BUT_RRF_LOW_RANK)

    if in_bm25 or in_semantic:
        best_source = min(
            rank for rank in (bm25_rank, semantic_rank) if rank is not None
        )
        if best_source > 10 and best_source <= retrieval_top_k:
            patterns.append(RetrievalPatternClassification.DEPTH_LIMITED)

    return tuple(patterns)


def build_observations(
    *,
    product_id: str,
    retrieval_top_k: int,
    bm25_rank: int | None,
    semantic_rank: int | None,
    rrf_rank: int | None,
) -> tuple[str, ...]:
    observations: list[str] = []
    if bm25_rank is None:
        observations.append(f"product {product_id} absent from BM25 top-{retrieval_top_k}")
    else:
        observations.append(f"product {product_id} appears in BM25 list at rank {bm25_rank}")
    if semantic_rank is None:
        observations.append(f"product {product_id} absent from semantic top-{retrieval_top_k}")
    else:
        observations.append(
            f"product {product_id} appears in semantic list at rank {semantic_rank}"
        )
    if rrf_rank is None:
        observations.append(f"product {product_id} absent from RRF top-{retrieval_top_k}")
    else:
        observations.append(f"product {product_id} appears in RRF list at rank {rrf_rank}")
    if (
        bm25_rank is not None
        and semantic_rank is not None
        and rrf_rank is not None
        and rrf_rank > bm25_rank
        and rrf_rank > semantic_rank
    ):
        observations.append(
            f"RRF rank {rrf_rank} is lower (worse) than both BM25 rank {bm25_rank} "
            f"and semantic rank {semantic_rank}"
        )
    return tuple(observations)


def build_interpretive_diagnostics(
    patterns: tuple[RetrievalPatternClassification, ...],
) -> tuple[str, ...]:
    mapping: dict[RetrievalPatternClassification, str] = {
        RetrievalPatternClassification.NOT_RETRIEVED_BY_EITHER: (
            "diagnostic: judged relevant product missing from both BM25 and semantic top-K "
            "(observed under incomplete judgments; not a proven catalog irrelevance)"
        ),
        RetrievalPatternClassification.BM25_ONLY: (
            "diagnostic: judged relevant product retrieved by BM25 but not semantic at top-K"
        ),
        RetrievalPatternClassification.SEMANTIC_ONLY: (
            "diagnostic: judged relevant product retrieved by semantic but not BM25 at top-K"
        ),
        RetrievalPatternClassification.RETRIEVED_BY_BOTH: (
            "diagnostic: judged relevant product retrieved by both BM25 and semantic at top-K"
        ),
        RetrievalPatternClassification.RETRIEVED_BUT_RRF_LOW_RANK: (
            "diagnostic: RRF fused rank is worse than at least one source rank "
            "(rank-based fusion effect; not a proven scoring defect)"
        ),
        RetrievalPatternClassification.DEPTH_LIMITED: (
            "diagnostic: judged relevant product appears only at depth > 10 in at least one "
            "source list within top-K (candidate depth constraint may limit recall@10)"
        ),
    }
    return tuple(mapping[pattern] for pattern in patterns if pattern in mapping)


def representation_review_candidate(
    patterns: tuple[RetrievalPatternClassification, ...],
    *,
    rrf_rank: int | None,
    retrieval_top_k: int,
) -> bool:
    if RetrievalPatternClassification.NOT_RETRIEVED_BY_EITHER in patterns:
        return True
    if RetrievalPatternClassification.DEPTH_LIMITED in patterns:
        return True
    if RetrievalPatternClassification.RETRIEVED_BUT_RRF_LOW_RANK in patterns:
        return True
    return rrf_rank is None or rrf_rank > min(20, retrieval_top_k)


def build_product_representation_evidence(
    product_id: str,
    catalog_row: Mapping[str, Any] | None,
) -> ProductRepresentationEvidence:
    if catalog_row is None:
        return ProductRepresentationEvidence(product_id=product_id, catalog_row_present=False)
    fields: dict[str, Any] = {}
    for name in REPRESENTATION_EVIDENCE_FIELD_NAMES:
        if name == "description":
            value = catalog_row.get("product_text")
        else:
            value = catalog_row.get(name)
        if value is not None:
            fields[name] = value
    return ProductRepresentationEvidence(
        product_id=product_id,
        catalog_row_present=True,
        fields=fields,
    )


def analyze_query_product(
    query: QueryRetrievalArtifactSlice,
    product_id: str,
    *,
    retrieval_top_k: int,
    rrf_rank_constant: int,
    catalog_row: Mapping[str, Any] | None,
    include_representation_evidence: bool,
) -> QueryProductDiagnosticRecord:
    bm25_ranks = build_rank_lookup(query.bm25_retrieved_product_ids, source_label="BM25")
    semantic_ranks = build_rank_lookup(
        query.semantic_retrieved_product_ids, source_label="semantic"
    )
    rrf_ranks = build_rank_lookup(query.rrf_retrieved_product_ids, source_label="RRF")

    bm25_rank = bm25_ranks.get(product_id)
    semantic_rank = semantic_ranks.get(product_id)
    rrf_rank = rrf_ranks.get(product_id)

    bm25_class = (
        Bm25ObservedClassification.RETRIEVED_BY_BM25
        if bm25_rank is not None
        else Bm25ObservedClassification.NOT_RETRIEVED_BY_BM25
    )
    semantic_class = (
        SemanticObservedClassification.RETRIEVED_BY_SEMANTIC
        if semantic_rank is not None
        else SemanticObservedClassification.NOT_RETRIEVED_BY_SEMANTIC
    )

    fusion_score = compute_rrf_score(
        bm25_rank=bm25_rank,
        vector_rank=semantic_rank,
        rank_constant=rrf_rank_constant,
    )
    vector_native = query.semantic_native_scores.get(product_id)

    patterns = derive_retrieval_pattern_classifications(
        bm25_rank=bm25_rank,
        semantic_rank=semantic_rank,
        rrf_rank=rrf_rank,
        retrieval_top_k=retrieval_top_k,
    )
    review = representation_review_candidate(
        patterns, rrf_rank=rrf_rank, retrieval_top_k=retrieval_top_k
    )
    evidence = None
    if include_representation_evidence and review:
        evidence = build_product_representation_evidence(product_id, catalog_row)

    return QueryProductDiagnosticRecord(
        query_id=query.query_id,
        query_text=query.query_text,
        query_category=query.category,
        product_id=product_id,
        relevance_judgment=RELEVANCE_JUDGMENT_JUDGED_RELEVANT,
        retrieval_top_k=retrieval_top_k,
        bm25=_method_snapshot(
            rank=bm25_rank,
            native_score=None,
            retrieval_top_k=retrieval_top_k,
        ),
        semantic=_method_snapshot(
            rank=semantic_rank,
            native_score=vector_native,
            retrieval_top_k=retrieval_top_k,
        ),
        rrf=RrfRetrievalSnapshot(
            retrieved=rrf_rank is not None,
            rank=rrf_rank,
            fusion_score=fusion_score if (bm25_rank or semantic_rank) else None,
            bm25_rank=bm25_rank,
            vector_rank=semantic_rank,
            bm25_native_score=None,
            vector_native_score=vector_native,
            depth=depth_snapshot(rrf_rank, retrieval_top_k=retrieval_top_k),
        ),
        bm25_observed_classification=bm25_class,
        semantic_observed_classification=semantic_class,
        retrieval_pattern_classifications=patterns,
        observations=build_observations(
            product_id=product_id,
            retrieval_top_k=retrieval_top_k,
            bm25_rank=bm25_rank,
            semantic_rank=semantic_rank,
            rrf_rank=rrf_rank,
        ),
        interpretive_diagnostics=build_interpretive_diagnostics(patterns),
        representation_evidence=evidence,
        representation_review_candidate=review,
    )


def analyze_retrieval_failures(
    *,
    productiq_version: str,
    lineage: FailureAnalysisLineage,
    queries: tuple[QueryRetrievalArtifactSlice, ...],
    catalog_rows_by_product_id: Mapping[str, Mapping[str, Any]] | None = None,
    include_representation_evidence: bool = True,
) -> RetrievalFailureAnalysisReport:
    catalog = catalog_rows_by_product_id or {}
    diagnostics: list[QueryProductDiagnosticRecord] = []
    for query in queries:
        for product_id in query.judged_relevant_product_ids:
            row = catalog.get(product_id)
            diagnostics.append(
                analyze_query_product(
                    query,
                    product_id,
                    retrieval_top_k=lineage.retrieval_top_k,
                    rrf_rank_constant=lineage.rrf_rank_constant,
                    catalog_row=row,
                    include_representation_evidence=include_representation_evidence,
                )
            )
    diagnostics.sort(key=lambda row: (row.query_id, row.product_id))
    judged_count = sum(len(query.judged_relevant_product_ids) for query in queries)
    return RetrievalFailureAnalysisReport(
        productiq_version=productiq_version,
        lineage=lineage,
        query_count=len(queries),
        judged_relevant_product_count=judged_count,
        diagnostics=tuple(diagnostics),
    )


__all__ = [
    "QueryRetrievalArtifactSlice",
    "analyze_query_product",
    "analyze_retrieval_failures",
    "build_interpretive_diagnostics",
    "build_observations",
    "build_product_representation_evidence",
    "build_rank_lookup",
    "depth_snapshot",
    "derive_retrieval_pattern_classifications",
    "representation_review_candidate",
]
