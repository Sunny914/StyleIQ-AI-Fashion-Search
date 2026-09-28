"""Tests for Phase 11.4 recommendation feature engineering."""

from __future__ import annotations

import math

import numpy as np
import pytest
from pydantic import ValidationError

from productiq.exceptions import RecommendationError
from productiq.recommendation.catalog_context_features import extract_catalog_context_features
from productiq.recommendation.contracts import (
    RecommendationCandidate,
    RecommendationCandidateSource,
)
from productiq.recommendation.feature_extractor import (
    extract_features,
    extract_features_for_candidates,
)
from productiq.recommendation.feature_matrix import (
    ORDERED_RECOMMENDATION_FEATURE_NAMES,
    build_recommendation_feature_matrix,
    vectorize_recommendation_features,
)
from productiq.recommendation.feature_schema import (
    RECOMMENDATION_FEATURE_SCHEMA_VERSION,
    RecommendationFeatures,
)
from productiq.recommendation.generation_features import extract_generation_features
from productiq.recommendation.product_context import RecommendationProductContext
from productiq.recommendation.similarity_features import extract_similarity_features
from productiq.recommendation.similarity_schema import (
    ContentSimilarity,
    MultiValueAttributeSimilarity,
    ScalarAttributeSimilarity,
    StructuredProductSimilarity,
)
from productiq.recommendation.structured_match_features import extract_structured_match_features
from productiq.representation.filtering import FilteringRepresentation
from productiq.representation.schema import ProductRepresentation


def _product(product_id: str) -> ProductRepresentation:
    return ProductRepresentation(
        product_id=product_id,
        brand="nike",
        brand_normalized="nike",
        category_gender="Women",
        product_type="t_shirt",
        color=["black"],
    )


def _filtering(product_id: str, *, discount: int = 1000, original: int = 1200) -> FilteringRepresentation:
    return FilteringRepresentation(
        product_id=product_id,
        source="ajio",
        brand="nike",
        brand_normalized="nike",
        category_gender="Women",
        product_type="t_shirt",
        color_raw="black",
        color_is_coded=True,
        color=["black"],
        pattern=None,
        material=None,
        fit=None,
        sleeve=None,
        neckline=None,
        product_features=None,
        style_attributes=None,
        discount_price_inr=discount,
        original_price_inr=original,
        price_anomaly=False,
    )


def _candidate(
    product_id: str,
    *,
    sources: tuple[RecommendationCandidateSource, ...] = (RecommendationCandidateSource.VECTOR,),
    score: float | None = 0.9,
) -> RecommendationCandidate:
    return RecommendationCandidate(
        product_id=product_id,
        sources=sources,
        candidate_generation_score=score,
    )


def _similarity(
    product_id: str,
    *,
    semantic: float | None = 0.8,
    lexical: float | None = 0.5,
    brand: float | None = 1.0,
) -> ContentSimilarity:
    return ContentSimilarity(
        product_id=product_id,
        semantic_similarity=semantic,
        lexical_similarity=lexical,
        structured=StructuredProductSimilarity(
            scalars=ScalarAttributeSimilarity(brand=brand),
            multivalue=MultiValueAttributeSimilarity(color=0.5),
        ),
    )


def _context(product_id: str, *, with_filtering: bool = True) -> RecommendationProductContext:
    return RecommendationProductContext(
        product_id=product_id,
        filtering=_filtering(product_id) if with_filtering else None,
    )


class TestFeatureContract:
    def test_immutable_and_versioned(self) -> None:
        row = RecommendationFeatures(
            product_id="P1",
            generation=extract_generation_features(_candidate("P1")),
            similarity=extract_similarity_features(_similarity("P1")),
            structured=extract_structured_match_features(_similarity("P1")),
            catalog=extract_catalog_context_features(_filtering("P1")),
        )
        assert row.feature_schema_version == RECOMMENDATION_FEATURE_SCHEMA_VERSION
        with pytest.raises(ValidationError):
            row.product_id = "P2"  # type: ignore[misc]

    def test_rejects_non_finite_similarity_feature(self) -> None:
        with pytest.raises(ValidationError):
            extract_similarity_features(_similarity("P1", semantic=float("inf")))

    def test_ordered_feature_names_length(self) -> None:
        assert len(ORDERED_RECOMMENDATION_FEATURE_NAMES) == 25


class TestGenerationFeatures:
    def test_vector_source(self) -> None:
        group = extract_generation_features(_candidate("P1"))
        assert group.retrieved_by_vector is True
        assert group.retrieved_by_attribute is False
        assert group.retrieved_by_bm25 is False
        assert group.source_count == 1
        assert group.retrieved_by_multiple_sources is False

    def test_multi_source_provenance(self) -> None:
        group = extract_generation_features(
            _candidate(
                "P1",
                sources=(
                    RecommendationCandidateSource.ATTRIBUTE,
                    RecommendationCandidateSource.BM25,
                    RecommendationCandidateSource.VECTOR,
                ),
            )
        )
        assert group.retrieved_by_vector is True
        assert group.retrieved_by_attribute is True
        assert group.retrieved_by_bm25 is True
        assert group.source_count == 3
        assert group.retrieved_by_multiple_sources is True

    def test_generation_score_preserved(self) -> None:
        group = extract_generation_features(_candidate("P1", score=0.123))
        assert group.candidate_generation_score == pytest.approx(0.123)


class TestSimilarityAndStructuredPropagation:
    def test_similarity_copied(self) -> None:
        sim = _similarity("P1", semantic=0.77, lexical=0.33)
        features = extract_features(
            seed_product=_product("S1"),
            candidate=_candidate("P1"),
            similarity=sim,
            context=_context("P1", with_filtering=False),
        )
        assert features.similarity.semantic_similarity == pytest.approx(0.77)
        assert features.similarity.lexical_similarity == pytest.approx(0.33)
        assert features.structured.brand_match == pytest.approx(1.0)
        assert features.structured.color_overlap == pytest.approx(0.5)

    def test_missing_similarity_stays_none(self) -> None:
        sim = _similarity("P1", semantic=None, lexical=None, brand=None)
        features = extract_features(
            seed_product=_product("S1"),
            candidate=_candidate("P1"),
            similarity=sim,
            context=_context("P1", with_filtering=False),
        )
        assert features.similarity.semantic_similarity is None
        assert features.structured.brand_match is None


class TestCatalogContext:
    def test_prices_copied(self) -> None:
        features = extract_features(
            seed_product=_product("S1"),
            candidate=_candidate("P1"),
            similarity=_similarity("P1"),
            context=_context("P1"),
        )
        assert features.catalog.discount_price_inr == 1000
        assert features.catalog.original_price_inr == 1200
        assert features.catalog.discount_amount_inr == 200

    def test_seed_price_deltas(self) -> None:
        features = extract_features(
            seed_product=_product("S1"),
            candidate=_candidate("P1"),
            similarity=_similarity("P1"),
            context=_context("P1", with_filtering=True),
            seed_filtering=_filtering("S1", discount=800, original=1000),
        )
        assert features.catalog.discount_price_delta_from_seed_inr == 200
        assert features.catalog.original_price_delta_from_seed_inr == 200

    def test_no_filtering_leaves_catalog_empty(self) -> None:
        features = extract_features(
            seed_product=_product("S1"),
            candidate=_candidate("P1"),
            similarity=_similarity("P1"),
            context=_context("P1", with_filtering=False),
        )
        assert features.catalog.discount_price_inr is None


class TestAlignment:
    def test_mismatched_similarity_id(self) -> None:
        with pytest.raises(RecommendationError, match="does not match"):
            extract_features(
                seed_product=_product("S1"),
                candidate=_candidate("P1"),
                similarity=_similarity("P2"),
                context=_context("P1", with_filtering=False),
            )

    def test_missing_context_in_batch(self) -> None:
        with pytest.raises(RecommendationError, match="missing RecommendationProductContext"):
            extract_features_for_candidates(
                seed_product=_product("S1"),
                candidates=(_candidate("P1"),),
                similarities_by_product_id={"P1": _similarity("P1")},
                context_by_product_id={},
            )

    def test_duplicate_candidate_ids(self) -> None:
        with pytest.raises(RecommendationError, match="duplicate candidate"):
            extract_features_for_candidates(
                seed_product=_product("S1"),
                candidates=(_candidate("P1"), _candidate("P1")),
                similarities_by_product_id={"P1": _similarity("P1")},
                context_by_product_id={"P1": _context("P1", with_filtering=False)},
            )


class TestBatchAndDeterminism:
    def test_batch_matches_individual(self) -> None:
        seed = _product("S1")
        candidates = (_candidate("P1"), _candidate("P2"))
        sims = {"P1": _similarity("P1"), "P2": _similarity("P2", semantic=0.1)}
        contexts = {
            "P1": _context("P1", with_filtering=False),
            "P2": _context("P2", with_filtering=False),
        }
        batch = extract_features_for_candidates(
            seed_product=seed,
            candidates=candidates,
            similarities_by_product_id=sims,
            context_by_product_id=contexts,
        )
        individual = tuple(
            extract_features(
                seed_product=seed,
                candidate=candidate,
                similarity=sims[candidate.product_id],
                context=contexts[candidate.product_id],
            )
            for candidate in candidates
        )
        assert batch == individual

    def test_stable_ordering(self) -> None:
        vector = vectorize_recommendation_features(
            extract_features(
                seed_product=_product("S1"),
                candidate=_candidate("P1"),
                similarity=_similarity("P1", semantic=None),
                context=_context("P1", with_filtering=False),
            )
        )
        assert len(vector) == len(ORDERED_RECOMMENDATION_FEATURE_NAMES)
        assert math.isnan(vector[ORDERED_RECOMMENDATION_FEATURE_NAMES.index("similarity.semantic_similarity")])


class TestMatrixConversion:
    def test_none_becomes_nan_only_in_matrix(self) -> None:
        features = extract_features(
            seed_product=_product("S1"),
            candidate=_candidate("P1"),
            similarity=_similarity("P1", semantic=None),
            context=_context("P1", with_filtering=False),
        )
        assert features.similarity.semantic_similarity is None
        matrix = build_recommendation_feature_matrix((features,))
        semantic_index = ORDERED_RECOMMENDATION_FEATURE_NAMES.index("similarity.semantic_similarity")
        assert math.isnan(matrix.matrix[0, semantic_index])

    def test_matrix_feature_order(self) -> None:
        features = extract_features(
            seed_product=_product("S1"),
            candidate=_candidate("P1"),
            similarity=_similarity("P1"),
            context=_context("P1", with_filtering=False),
        )
        matrix = build_recommendation_feature_matrix((features,))
        assert matrix.feature_spec.feature_names == ORDERED_RECOMMENDATION_FEATURE_NAMES
        assert matrix.product_ids == ("P1",)
        assert matrix.matrix.shape == (1, len(ORDERED_RECOMMENDATION_FEATURE_NAMES))
        bool_index = ORDERED_RECOMMENDATION_FEATURE_NAMES.index("generation.retrieved_by_vector")
        assert matrix.matrix[0, bool_index] == pytest.approx(1.0)

    def test_matrix_row_order_follows_candidates(self) -> None:
        rows = extract_features_for_candidates(
            seed_product=_product("S1"),
            candidates=(_candidate("P2"), _candidate("P1")),
            similarities_by_product_id={
                "P1": _similarity("P1"),
                "P2": _similarity("P2"),
            },
            context_by_product_id={
                "P1": _context("P1", with_filtering=False),
                "P2": _context("P2", with_filtering=False),
            },
        )
        matrix = build_recommendation_feature_matrix(rows)
        assert matrix.product_ids == ("P2", "P1")
        assert np.all(np.isfinite(matrix.matrix[:, 0]))
