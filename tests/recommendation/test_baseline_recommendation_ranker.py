"""Tests for Phase 11.5 baseline recommendation ranker."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from productiq.exceptions import RecommendationError
from productiq.recommendation.baseline_ranker import (
    BaselineRecommendationRanker,
    rank_recommendations,
)
from productiq.recommendation.baseline_ranker_config import (
    BASELINE_RECOMMENDATION_RANKER_VERSION,
    BaselineRecommendationRankerConfig,
)
from productiq.recommendation.baseline_scoring import (
    breakdown_contribution_sum,
    compute_baseline_recommendation_score,
)
from productiq.recommendation.contracts import (
    RecommendationCandidate,
    RecommendationCandidateSource,
)
from productiq.recommendation.feature_schema import (
    CandidateGenerationFeatureGroup,
    CatalogContextFeatureGroup,
    RecommendationFeatures,
    SimilarityFeatureGroup,
    StructuredMatchFeatureGroup,
)
from productiq.recommendation.generation_features import extract_generation_features


def _minimal_features(
    product_id: str,
    *,
    semantic: float | None = None,
    lexical: float | None = None,
    brand_match: float | None = None,
    retrieved_by_vector: bool = False,
    catalog: CatalogContextFeatureGroup | None = None,
) -> RecommendationFeatures:
    return RecommendationFeatures(
        product_id=product_id,
        generation=CandidateGenerationFeatureGroup(
            retrieved_by_vector=retrieved_by_vector,
            retrieved_by_attribute=False,
            retrieved_by_bm25=False,
            retrieved_by_multiple_sources=False,
            source_count=1,
            candidate_generation_score=None,
        ),
        similarity=SimilarityFeatureGroup(
            semantic_similarity=semantic,
            lexical_similarity=lexical,
        ),
        structured=StructuredMatchFeatureGroup(brand_match=brand_match),
        catalog=catalog or CatalogContextFeatureGroup(),
    )


class TestBaselineConfiguration:
    def test_default_version_and_weights(self) -> None:
        config = BaselineRecommendationRankerConfig()
        assert config.ranker_version == BASELINE_RECOMMENDATION_RANKER_VERSION
        weights = config.weights
        assert weights.semantic_similarity == pytest.approx(0.20)
        assert sum(weights.model_dump().values()) == pytest.approx(1.05)

    def test_config_is_immutable(self) -> None:
        config = BaselineRecommendationRankerConfig()
        with pytest.raises(ValidationError):
            config.ranker_version = "x"  # type: ignore[misc]


class TestBasicScoring:
    def test_semantic_only_score(self) -> None:
        features = _minimal_features("P1", semantic=0.5)
        breakdown = compute_baseline_recommendation_score(features)
        assert breakdown.recommendation_score == pytest.approx(0.10)
        assert breakdown_contribution_sum(breakdown) == pytest.approx(breakdown.recommendation_score)

    def test_multiple_contributions(self) -> None:
        features = _minimal_features("P1", semantic=1.0, lexical=1.0, brand_match=1.0)
        breakdown = compute_baseline_recommendation_score(features)
        expected = 0.20 + 0.10 + 0.12
        assert breakdown.recommendation_score == pytest.approx(expected)


class TestMissingValues:
    def test_none_contributes_zero(self) -> None:
        features = _minimal_features("P1", semantic=None, brand_match=None)
        breakdown = compute_baseline_recommendation_score(features)
        assert breakdown.recommendation_score == pytest.approx(0.0)
        assert features.similarity.semantic_similarity is None
        assert features.structured.brand_match is None

    def test_missing_does_not_renormalize(self) -> None:
        features = _minimal_features("P1", semantic=1.0)
        score = compute_baseline_recommendation_score(features).recommendation_score
        assert score == pytest.approx(0.20)


class TestProvenanceAndStructured:
    def test_vector_flag_contribution(self) -> None:
        features = _minimal_features("P1", retrieved_by_vector=True)
        score = compute_baseline_recommendation_score(features).recommendation_score
        assert score == pytest.approx(0.03)

    def test_multi_source_contribution(self) -> None:
        candidate = RecommendationCandidate(
            product_id="P1",
            sources=(
                RecommendationCandidateSource.ATTRIBUTE,
                RecommendationCandidateSource.VECTOR,
            ),
            candidate_generation_score=0.5,
        )
        generation = extract_generation_features(candidate)
        features = RecommendationFeatures(
            product_id="P1",
            generation=generation,
            similarity=SimilarityFeatureGroup(),
            structured=StructuredMatchFeatureGroup(),
            catalog=CatalogContextFeatureGroup(),
        )
        score = compute_baseline_recommendation_score(features).recommendation_score
        assert score == pytest.approx(0.03 + 0.03 + 0.05)


class TestCatalogPriceExclusion:
    def test_raw_inr_does_not_affect_score(self) -> None:
        base = _minimal_features("P1", semantic=0.5)
        with_prices = _minimal_features(
            "P1",
            semantic=0.5,
            catalog=CatalogContextFeatureGroup(
                discount_price_inr=999_999,
                original_price_inr=1_999_999,
                discount_amount_inr=1_000_000,
                discount_price_delta_from_seed_inr=500_000,
            ),
        )
        assert compute_baseline_recommendation_score(base).recommendation_score == pytest.approx(
            compute_baseline_recommendation_score(with_prices).recommendation_score
        )


class TestRanking:
    def test_deterministic_order_and_tie_break(self) -> None:
        rows = (
            _minimal_features("P2", semantic=0.5),
            _minimal_features("P1", semantic=0.5),
            _minimal_features("P3", semantic=0.9),
        )
        first = rank_recommendations(rows, top_k=3)
        second = rank_recommendations(rows, top_k=3)
        assert first == second
        assert [row.product_id for row in first] == ["P3", "P1", "P2"]
        assert [row.rank for row in first] == [1, 2, 3]

    def test_top_k_truncation_and_contiguous_ranks(self) -> None:
        rows = tuple(_minimal_features(f"P{i}", semantic=float(i) / 10) for i in range(1, 6))
        ranked = rank_recommendations(rows, top_k=2)
        assert len(ranked) == 2
        assert [row.rank for row in ranked] == [1, 2]

    def test_empty_input(self) -> None:
        assert rank_recommendations((), top_k=5) == ()

    def test_seed_excluded_from_output(self) -> None:
        rows = (
            _minimal_features("SEED", semantic=1.0),
            _minimal_features("P2", semantic=0.1),
        )
        ranked = rank_recommendations(rows, top_k=5, seed_product_id="SEED")
        assert all(row.product_id != "SEED" for row in ranked)

    def test_duplicate_feature_ids_rejected(self) -> None:
        row = _minimal_features("P1", semantic=0.5)
        with pytest.raises(RecommendationError, match="unique product_id"):
            rank_recommendations((row, row), top_k=5)

    def test_invalid_top_k(self) -> None:
        with pytest.raises(RecommendationError, match="top_k must be positive"):
            rank_recommendations((_minimal_features("P1"),), top_k=0)


class TestExplainability:
    def test_contribution_details(self) -> None:
        features = _minimal_features("P1", semantic=0.91)
        breakdown = compute_baseline_recommendation_score(features)
        semantic_row = next(
            row for row in breakdown.contributions if row.feature_name == "similarity.semantic_similarity"
        )
        assert semantic_row.feature_value == pytest.approx(0.91)
        assert semantic_row.weight == pytest.approx(0.20)
        assert semantic_row.contribution == pytest.approx(0.182)


class TestRankerClass:
    def test_baseline_ranker_wrapper(self) -> None:
        ranker = BaselineRecommendationRanker()
        ranked = ranker.rank((_minimal_features("P1", semantic=1.0),), top_k=1)
        assert ranked[0].recommendation_score == pytest.approx(0.20)


class TestNonFiniteScoreContract:
    def test_breakdown_rejects_non_finite_score(self) -> None:
        from productiq.recommendation.baseline_scoring import BaselineRecommendationScoreBreakdown

        with pytest.raises(ValidationError):
            BaselineRecommendationScoreBreakdown(
                product_id="P1",
                recommendation_score=float("nan"),
                contributions=(),
            )
