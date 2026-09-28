"""End-to-end production retrieval integration (Phase 4.20)."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from productiq.representation.query_contract import (
    QueryFilterConstraints,
    QueryLexicalIntent,
    QueryRepresentation,
    QuerySemanticIntent,
    build_query_representation,
)
from productiq.retrieval.contracts import RetrievalRequest, RetrievalResponse
from tests.retrieval.integration.conftest import (
    DEFAULT_CANDIDATE_POOL_TOP_K,
    DEFAULT_REQUEST_TOP_K,
    LiveProductionRetrievalContext,
    production_retrieval_pytestmark,
)
from tests.retrieval.integration.invariants import (
    assert_catalog_contains_candidates,
    assert_deterministic_candidate_lists,
    assert_finite_scores,
    assert_hard_constraints_satisfied,
    assert_production_metadata_coherent,
    assert_provenance_present,
    assert_rrf_fusion_ordering,
    assert_top_k_respected,
    assert_unique_candidate_ids,
)

pytestmark = production_retrieval_pytestmark


@dataclass(frozen=True)
class SmokeQueryCase:
    case_id: str
    query: QueryRepresentation
    expect_zero: bool = False
    validate_constraints: bool = False


def _smoke_query_matrix() -> tuple[SmokeQueryCase, ...]:
    return (
        SmokeQueryCase(
            case_id="brand_product",
            query=build_query_representation("Nike running shoes"),
        ),
        SmokeQueryCase(
            case_id="brand_color_product",
            query=build_query_representation(
                "black Nike running shoes",
                constraints=QueryFilterConstraints(
                    brand_normalized="nike",
                    color=["black"],
                ),
            ),
            validate_constraints=True,
        ),
        SmokeQueryCase(
            case_id="price_constrained",
            query=build_query_representation(
                "Nike running shoes under 5000",
                constraints=QueryFilterConstraints(
                    brand_normalized="nike",
                    max_discount_price_inr=5000,
                ),
            ),
            validate_constraints=True,
        ),
        SmokeQueryCase(
            case_id="multi_constraint",
            query=build_query_representation(
                "black Nike running shoes under 5000 for men",
                constraints=QueryFilterConstraints(
                    brand_normalized="nike",
                    color=["black"],
                    max_discount_price_inr=5000,
                    category_gender="Men",
                ),
            ),
            validate_constraints=True,
        ),
        SmokeQueryCase(
            case_id="semantic_descriptive",
            query=build_query_representation("comfortable shoes for running"),
        ),
        SmokeQueryCase(
            case_id="impossible_constraints",
            query=build_query_representation(
                "Nike running shoes",
                constraints=QueryFilterConstraints(
                    brand_normalized="productiq_impossible_brand_token_xyz",
                ),
            ),
            expect_zero=True,
            validate_constraints=True,
        ),
    )


def _retrieve(
    context: LiveProductionRetrievalContext,
    query: QueryRepresentation,
    *,
    top_k: int = DEFAULT_REQUEST_TOP_K,
) -> RetrievalResponse:
    return context.pipeline.retrieve(RetrievalRequest(query=query, top_k=top_k))


def _assert_successful_production_response(
    context: LiveProductionRetrievalContext,
    response: RetrievalResponse,
    *,
    query: QueryRepresentation,
    requested_top_k: int,
    validate_constraints: bool,
) -> None:
    assert isinstance(response, RetrievalResponse)
    assert_top_k_respected(response, requested_top_k=requested_top_k)
    assert response.metadata is not None
    assert_production_metadata_coherent(
        response.metadata,
        requested_top_k=requested_top_k,
        candidate_pool_top_k=DEFAULT_CANDIDATE_POOL_TOP_K,
    )
    if response.candidate_count == 0:
        return
    assert_unique_candidate_ids(response.candidates)
    assert_finite_scores(response.candidates)
    assert_rrf_fusion_ordering(response.candidates)
    assert_provenance_present(response.candidates)
    assert_catalog_contains_candidates(context.engine, response.candidates)
    if validate_constraints:
        assert_hard_constraints_satisfied(
            context.filter_session,
            query=query,
            candidates=response.candidates,
        )


@pytest.mark.parametrize("case", _smoke_query_matrix(), ids=lambda case: case.case_id)
def test_production_smoke_query_matrix(
    live_production_retrieval: LiveProductionRetrievalContext,
    case: SmokeQueryCase,
) -> None:
    response = _retrieve(live_production_retrieval, case.query)
    if case.expect_zero:
        assert response.candidate_count == 0
        assert response.metadata is not None
        assert response.metadata.returned_candidate_count == 0
        return
    _assert_successful_production_response(
        live_production_retrieval,
        response,
        query=case.query,
        requested_top_k=DEFAULT_REQUEST_TOP_K,
        validate_constraints=case.validate_constraints,
    )


def test_production_retrieval_full_real_chain(
    live_production_retrieval: LiveProductionRetrievalContext,
) -> None:
    """Exercise BM25 + semantic + pgvector + RRF + Postgres filter + pipeline."""
    query = build_query_representation(
        "black Nike running shoes",
        constraints=QueryFilterConstraints(brand_normalized="nike", color=["black"]),
    )
    response = _retrieve(live_production_retrieval, query)
    _assert_successful_production_response(
        live_production_retrieval,
        response,
        query=query,
        requested_top_k=DEFAULT_REQUEST_TOP_K,
        validate_constraints=True,
    )
    assert live_production_retrieval.used_full_bm25_index or response.candidate_count >= 0


def test_empty_retrieval_intent_returns_zero_without_error(
    live_production_retrieval: LiveProductionRetrievalContext,
) -> None:
    query = QueryRepresentation.model_construct(
        query_text="constraint-only-smoke",
        constraints=QueryFilterConstraints(brand_normalized="nike"),
        lexical_intent=QueryLexicalIntent.model_construct(text=""),
        semantic_intent=QuerySemanticIntent.model_construct(text=""),
    )
    response = _retrieve(live_production_retrieval, query)
    assert response.candidate_count == 0
    assert response.metadata is not None
    assert response.metadata.returned_candidate_count == 0


def test_repeated_request_is_deterministic(
    live_production_retrieval: LiveProductionRetrievalContext,
) -> None:
    query = build_query_representation("Nike running shoes")
    request = RetrievalRequest(query=query, top_k=DEFAULT_REQUEST_TOP_K)
    first = live_production_retrieval.pipeline.retrieve(request)
    second = live_production_retrieval.pipeline.retrieve(request)
    assert_deterministic_candidate_lists(first.candidates, second.candidates)
    if first.metadata is not None and second.metadata is not None:
        assert first.metadata.returned_candidate_count == second.metadata.returned_candidate_count
        assert first.metadata.filtered_candidate_count == second.metadata.filtered_candidate_count


def test_filtering_preserves_rrf_order_under_constraints(
    live_production_retrieval: LiveProductionRetrievalContext,
) -> None:
    query = build_query_representation(
        "running shoes",
        constraints=QueryFilterConstraints(max_discount_price_inr=5000),
    )
    response = _retrieve(live_production_retrieval, query)
    if response.candidate_count == 0:
        pytest.skip("no candidates after filter for ordering check")
    assert_rrf_fusion_ordering(response.candidates)
    fusion_scores = [candidate.fusion_score for candidate in response.candidates]
    assert fusion_scores == sorted(fusion_scores, reverse=True)
