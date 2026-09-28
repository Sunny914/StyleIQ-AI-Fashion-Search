"""Tests for Phase 10.2 ranking feature engineering."""

from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from productiq.exceptions import RankingError
from productiq.ranking.adapters import ranking_candidate_from_retrieval
from productiq.ranking.contracts import RankingCandidate, RankingRequest
from productiq.ranking.feature_extractor import extract_features, extract_features_for_request
from productiq.ranking.feature_schema import RankingFeatures, ranking_features_to_dict
from productiq.ranking.matching_features import extract_matching_features
from productiq.ranking.product_context import RankingProductContext
from productiq.ranking.retrieval_features import extract_retrieval_features
from productiq.representation.builder import build_product_representation
from productiq.representation.filtering import build_filtering_representation_from_canonical
from productiq.representation.query_contract import (
    QueryFilterConstraints,
    build_query_representation,
)
from productiq.retrieval.contracts import RetrievalCandidate, RetrievalMethod
from tests.database.catalog_fixtures import make_product_record


def _product_context(**overrides: object) -> RankingProductContext:
    record = make_product_record(**overrides)
    product = build_product_representation(record)
    filtering = build_filtering_representation_from_canonical(record)
    return RankingProductContext(
        product_id=product.product_id,
        product=product,
        filtering=filtering,
    )


def _ranking_candidate(retrieval: RetrievalCandidate) -> RankingCandidate:
    return ranking_candidate_from_retrieval(retrieval)


def test_retrieval_features_bm25_only() -> None:
    retrieval = RetrievalCandidate(product_id="P1", score=3.5, method=RetrievalMethod.BM25)
    features = extract_retrieval_features(retrieval)
    assert features.bm25_score == pytest.approx(3.5)
    assert features.retrieved_by_bm25 is True
    assert features.retrieved_by_vector is False
    assert features.retrieved_by_both is False
    assert features.vector_similarity is None
    assert features.rrf_score is None


def test_retrieval_features_vector_only() -> None:
    retrieval = RetrievalCandidate(product_id="P2", score=0.77, method=RetrievalMethod.VECTOR)
    features = extract_retrieval_features(retrieval)
    assert features.vector_similarity == pytest.approx(0.77)
    assert features.retrieved_by_vector is True
    assert features.bm25_score is None


def test_retrieval_features_hybrid_rrf_preserves_ranks() -> None:
    retrieval = RetrievalCandidate(
        product_id="P3",
        score=0.04,
        fusion_score=0.04,
        method=RetrievalMethod.HYBRID,
        retrieval_methods=(RetrievalMethod.BM25, RetrievalMethod.VECTOR),
        bm25_score=2.0,
        vector_score=0.8,
        bm25_rank=2,
        vector_rank=5,
    )
    features = extract_retrieval_features(retrieval)
    assert features.rrf_score == pytest.approx(0.04)
    assert features.bm25_rank == 2
    assert features.vector_rank == 5
    assert features.retrieved_by_both is True


def test_retrieval_features_rejects_nan_in_schema() -> None:
    with pytest.raises(ValidationError):
        RankingFeatures(
            product_id="P1",
            retrieval={
                "bm25_score": math.nan,
                "retrieved_by_bm25": True,
                "retrieved_by_vector": False,
                "retrieved_by_both": False,
            },
            matching={"matched_attribute_count": 0},
            catalog={},
        )


def test_brand_match_on_normalized_values() -> None:
    context = _product_context(brand_normalized="nike")
    query = build_query_representation(
        "shoes",
        constraints=QueryFilterConstraints(brand_normalized="nike"),
    )
    matching = extract_matching_features(query, context.product, filtering=context.filtering)
    assert matching.brand_match is True
    assert matching.constraint_match is True


def test_brand_mismatch() -> None:
    context = _product_context(brand_normalized="adidas")
    query = build_query_representation(
        "shoes",
        constraints=QueryFilterConstraints(brand_normalized="nike"),
    )
    matching = extract_matching_features(query, context.product, filtering=context.filtering)
    assert matching.brand_match is False
    assert matching.constraint_match is False


def test_color_multivalue_match() -> None:
    record = make_product_record(color_normalized="blue|navy")
    product = build_product_representation(record)
    filtering = build_filtering_representation_from_canonical(record)
    query = build_query_representation(
        "shirt",
        constraints=QueryFilterConstraints(color=["blue"]),
    )
    matching = extract_matching_features(query, product, filtering=filtering)
    assert matching.color_match is True


def test_attribute_overlap_partial() -> None:
    context = _product_context(brand_normalized="nike", product_type="shirt")
    query = build_query_representation(
        "x",
        constraints=QueryFilterConstraints(
            brand_normalized="nike",
            product_type="shoes",
        ),
    )
    matching = extract_matching_features(query, context.product, filtering=context.filtering)
    assert matching.matched_attribute_count == 1
    assert matching.attribute_overlap == pytest.approx(0.5)


def test_attribute_overlap_zero_requested_attributes() -> None:
    query = build_query_representation("plain query")
    context = _product_context()
    matching = extract_matching_features(query, context.product, filtering=context.filtering)
    assert matching.matched_attribute_count == 0
    assert matching.attribute_overlap is None


def test_constraint_match_none_without_constraints() -> None:
    context = _product_context()
    query = build_query_representation("plain query")
    matching = extract_matching_features(query, context.product, filtering=context.filtering)
    assert matching.constraint_match is None


def test_catalog_features_from_filtering() -> None:
    context = _product_context(discount_price_inr=559, original_price_inr=999)
    features = extract_features(
        query=build_query_representation("shirt"),
        candidate=_ranking_candidate(
            RetrievalCandidate(product_id=context.product_id, score=1.0, method=RetrievalMethod.BM25),
        ),
        product_context=context,
    )
    assert features.catalog.discount_price_inr == 559
    assert features.catalog.original_price_inr == 999
    assert features.catalog.discount_amount_inr == 440


def test_catalog_features_missing_without_filtering_context() -> None:
    record = make_product_record()
    product = build_product_representation(record)
    context = RankingProductContext(product_id=product.product_id, product=product, filtering=None)
    features = extract_features(
        query=build_query_representation("shirt"),
        candidate=_ranking_candidate(
            RetrievalCandidate(product_id=product.product_id, score=1.0, method=RetrievalMethod.BM25),
        ),
        product_context=context,
    )
    assert features.catalog.discount_price_inr is None


def test_extract_features_for_request_preserves_order() -> None:
    context_a = _product_context(product_id="123456789001")
    context_b = _product_context(product_id="123456789002")
    request = RankingRequest(
        query=build_query_representation("shoes"),
        candidates=(
            _ranking_candidate(
                RetrievalCandidate(product_id=context_a.product_id, score=1.0, method=RetrievalMethod.BM25),
            ),
            _ranking_candidate(
                RetrievalCandidate(product_id=context_b.product_id, score=0.5, method=RetrievalMethod.VECTOR),
            ),
        ),
        top_k=2,
    )
    snapshot = request.candidates
    rows = extract_features_for_request(
        request,
        product_context_by_id={
            context_a.product_id: context_a,
            context_b.product_id: context_b,
        },
    )
    assert request.candidates == snapshot
    assert [row.product_id for row in rows] == [context_a.product_id, context_b.product_id]


def test_extract_features_deterministic() -> None:
    context = _product_context()
    candidate = _ranking_candidate(
        RetrievalCandidate(product_id=context.product_id, score=0.2, method=RetrievalMethod.VECTOR),
    )
    query = build_query_representation("running")
    first = extract_features(query=query, candidate=candidate, product_context=context)
    second = extract_features(query=query, candidate=candidate, product_context=context)
    assert first.model_dump() == second.model_dump()


def test_extract_features_for_request_missing_context_raises() -> None:
    context = _product_context()
    request = RankingRequest(
        query=build_query_representation("x"),
        candidates=(
            _ranking_candidate(
                RetrievalCandidate(product_id="missing-id", score=1.0, method=RetrievalMethod.BM25),
            ),
        ),
        top_k=1,
    )
    with pytest.raises(RankingError, match="missing RankingProductContext"):
        extract_features_for_request(request, product_context_by_id={context.product_id: context})


def test_ranking_features_serialization_roundtrip() -> None:
    context = _product_context()
    features = extract_features(
        query=build_query_representation("x"),
        candidate=_ranking_candidate(
            RetrievalCandidate(product_id=context.product_id, score=1.0, method=RetrievalMethod.BM25),
        ),
        product_context=context,
    )
    payload = ranking_features_to_dict(features)
    restored = RankingFeatures.model_validate(payload)
    assert restored == features
