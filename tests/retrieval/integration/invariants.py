"""Shared assertion helpers for retrieval integration tests (Phase 4.20)."""

from __future__ import annotations

import math

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from productiq.database.models.product import Product
from productiq.representation.query_contract import QueryRepresentation
from productiq.retrieval.catalog_candidate_filter import filtering_representation_from_product
from productiq.retrieval.catalog_constraint_match import (
    constraints_are_active,
    filtering_satisfies_query_constraints,
)
from productiq.retrieval.contracts import (
    RetrievalCandidate,
    RetrievalMethod,
    RetrievalResponse,
    RetrievalResponseMetadata,
)


def assert_unique_candidate_ids(candidates: tuple[RetrievalCandidate, ...]) -> None:
    product_ids = [candidate.product_id for candidate in candidates]
    assert len(product_ids) == len(set(product_ids))


def assert_finite_scores(candidates: tuple[RetrievalCandidate, ...]) -> None:
    for candidate in candidates:
        assert math.isfinite(candidate.score)
        for optional_score in (candidate.bm25_score, candidate.vector_score, candidate.fusion_score):
            if optional_score is not None:
                assert math.isfinite(optional_score)


def assert_top_k_respected(response: RetrievalResponse, *, requested_top_k: int) -> None:
    assert response.candidate_count <= requested_top_k


def assert_rrf_fusion_ordering(candidates: tuple[RetrievalCandidate, ...]) -> None:
    previous_fusion: float | None = None
    for candidate in candidates:
        assert candidate.method is RetrievalMethod.HYBRID
        assert candidate.fusion_score is not None
        if previous_fusion is not None:
            assert candidate.fusion_score <= previous_fusion + 1e-12
        previous_fusion = candidate.fusion_score


def assert_provenance_present(candidates: tuple[RetrievalCandidate, ...]) -> None:
    for candidate in candidates:
        methods = candidate.resolved_retrieval_methods()
        assert methods
        if RetrievalMethod.BM25 in methods:
            assert candidate.bm25_score is not None
        if RetrievalMethod.VECTOR in methods:
            assert candidate.vector_score is not None
        assert candidate.fusion_score is not None
        assert candidate.score == candidate.fusion_score


def assert_catalog_contains_candidates(engine: Engine, candidates: tuple[RetrievalCandidate, ...]) -> None:
    if not candidates:
        return
    product_ids = [candidate.product_id for candidate in candidates]
    with engine.connect() as connection:
        found_raw = connection.execute(
            text("SELECT COUNT(*) FROM products WHERE product_id = ANY(:ids)"),
            {"ids": product_ids},
        ).scalar_one()
    assert int(found_raw) == len(product_ids)


def assert_hard_constraints_satisfied(
    session: Session,
    *,
    query: QueryRepresentation,
    candidates: tuple[RetrievalCandidate, ...],
) -> None:
    constraints = query.constraints
    if constraints is None or not constraints_are_active(constraints):
        return
    for candidate in candidates:
        product = session.get(Product, candidate.product_id)
        assert product is not None, f"missing catalog row for {candidate.product_id}"
        filtering = filtering_representation_from_product(product)
        assert filtering_satisfies_query_constraints(filtering, constraints)


def assert_production_metadata_coherent(
    metadata: RetrievalResponseMetadata,
    *,
    requested_top_k: int,
    candidate_pool_top_k: int,
) -> None:
    assert metadata.requested_top_k == requested_top_k
    assert metadata.candidate_pool_top_k == candidate_pool_top_k
    assert metadata.returned_candidate_count is not None
    assert metadata.returned_candidate_count <= requested_top_k
    if metadata.filtered_candidate_count is not None:
        assert metadata.filtered_candidate_count >= metadata.returned_candidate_count
    if metadata.fused_candidate_count is not None and metadata.filtered_candidate_count is not None:
        assert metadata.filtered_candidate_count <= metadata.fused_candidate_count


def assert_deterministic_candidate_lists(
    first: tuple[RetrievalCandidate, ...],
    second: tuple[RetrievalCandidate, ...],
) -> None:
    assert len(first) == len(second)
    for left, right in zip(first, second, strict=True):
        assert left.product_id == right.product_id
        assert left.score == right.score
        assert left.fusion_score == right.fusion_score
        assert left.bm25_score == right.bm25_score
        assert left.vector_score == right.vector_score
        assert left.bm25_rank == right.bm25_rank
        assert left.vector_rank == right.vector_rank
        assert left.resolved_retrieval_methods() == right.resolved_retrieval_methods()


__all__ = [
    "assert_catalog_contains_candidates",
    "assert_deterministic_candidate_lists",
    "assert_finite_scores",
    "assert_hard_constraints_satisfied",
    "assert_production_metadata_coherent",
    "assert_provenance_present",
    "assert_rrf_fusion_ordering",
    "assert_top_k_respected",
    "assert_unique_candidate_ids",
]
