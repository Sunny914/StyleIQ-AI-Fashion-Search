"""Tests for Phase 11.6 recommendation selection and diversity."""

from __future__ import annotations

import pytest

from productiq.recommendation.contracts import (
    RankedRecommendation,
    RecommendationCandidate,
    RecommendationCandidateSource,
)
from productiq.recommendation.recommendation_selection import (
    select_recommendations,
    select_recommendations_with_diagnostics,
)
from productiq.recommendation.selection_config import RecommendationSelectionConfig
from productiq.recommendation.selection_context import RecommendationSelectionContext
from productiq.recommendation.selection_diagnostics import RecommendationSelectionRejectionReason
from productiq.representation.filtering import FilteringRepresentation
from productiq.representation.query_contract import QueryFilterConstraints
from productiq.representation.schema import ProductRepresentation


def _ranked(
    product_id: str,
    rank: int,
    score: float,
) -> RankedRecommendation:
    candidate = RecommendationCandidate(
        product_id=product_id,
        sources=(RecommendationCandidateSource.VECTOR,),
        candidate_generation_score=score,
    )
    return RankedRecommendation(
        product_id=product_id,
        rank=rank,
        recommendation_score=score,
        candidate=candidate,
    )


def _filtering(product_id: str, *, brand: str = "nike", product_type: str = "t_shirt") -> FilteringRepresentation:
    return FilteringRepresentation(
        product_id=product_id,
        source="ajio",
        brand=brand,
        brand_normalized=brand,
        category_gender="Women",
        product_type=product_type,
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
        discount_price_inr=1000,
        original_price_inr=1200,
        price_anomaly=False,
    )


class TestSeedAndDuplicates:
    def test_seed_excluded(self) -> None:
        rows = (_ranked("SEED", 1, 0.99), _ranked("P2", 2, 0.5))
        result = select_recommendations_with_diagnostics(
            rows,
            top_k=5,
            context=RecommendationSelectionContext(seed_product_id="SEED"),
        )
        assert [row.product_id for row in result.selected] == ["P2"]
        assert result.diagnostics[0].reason == RecommendationSelectionRejectionReason.SEED_EXCLUDED

    def test_duplicate_product_id_in_input(self) -> None:
        rows = (_ranked("P1", 1, 0.9), _ranked("P1", 2, 0.8))
        result = select_recommendations_with_diagnostics(rows, top_k=5)
        assert len(result.selected) == 1
        assert result.diagnostics[1].reason == RecommendationSelectionRejectionReason.DUPLICATE_PRODUCT


class TestBrandDiversity:
    def test_max_per_brand_quota(self) -> None:
        rows = (
            _ranked("P1", 1, 0.9),
            _ranked("P2", 2, 0.8),
            _ranked("P3", 3, 0.7),
            _ranked("P4", 4, 0.6),
        )
        filtering = {
            "P1": _filtering("P1", brand="nike"),
            "P2": _filtering("P2", brand="nike"),
            "P3": _filtering("P3", brand="nike"),
            "P4": _filtering("P4", brand="adidas"),
        }
        result = select_recommendations_with_diagnostics(
            rows,
            top_k=10,
            config=RecommendationSelectionConfig(max_per_brand=2),
            context=RecommendationSelectionContext(filtering_by_product_id=filtering),
        )
        assert [row.product_id for row in result.selected] == ["P1", "P2", "P4"]
        assert result.diagnostics[2].reason == RecommendationSelectionRejectionReason.MAX_PER_BRAND


class TestProductTypeDiversity:
    def test_max_per_product_type(self) -> None:
        rows = (
            _ranked("P1", 1, 0.9),
            _ranked("P2", 2, 0.8),
            _ranked("P3", 3, 0.7),
        )
        filtering = {
            "P1": _filtering("P1", product_type="running_shoe"),
            "P2": _filtering("P2", product_type="running_shoe"),
            "P3": _filtering("P3", product_type="running_shoe"),
        }
        result = select_recommendations_with_diagnostics(
            rows,
            top_k=5,
            config=RecommendationSelectionConfig(max_per_product_type=2),
            context=RecommendationSelectionContext(filtering_by_product_id=filtering),
        )
        assert [row.product_id for row in result.selected] == ["P1", "P2"]
        assert result.diagnostics[2].reason == RecommendationSelectionRejectionReason.MAX_PER_PRODUCT_TYPE


class TestMissingValues:
    def test_missing_brand_does_not_share_quota(self) -> None:
        products = {
            "P1": ProductRepresentation(product_id="P1", category_gender="Women", brand=None),
            "P2": ProductRepresentation(product_id="P2", category_gender="Women", brand=None),
        }
        rows = (_ranked("P1", 1, 0.9), _ranked("P2", 2, 0.8))
        selected = select_recommendations(
            rows,
            top_k=5,
            config=RecommendationSelectionConfig(max_per_brand=1),
            context=RecommendationSelectionContext(product_by_product_id=products),
        )
        assert len(selected) == 2


class TestScoreAndRankBehavior:
    def test_scores_unchanged(self) -> None:
        rows = (_ranked("P1", 1, 0.91), _ranked("P2", 2, 0.87))
        original = rows[1].recommendation_score
        selected = select_recommendations(rows, top_k=2)
        assert selected[1].recommendation_score == original

    def test_contiguous_ranks_after_skip(self) -> None:
        rows = (
            _ranked("P1", 1, 0.9),
            _ranked("P2", 2, 0.8),
            _ranked("P3", 3, 0.7),
        )
        filtering = {
            "P1": _filtering("P1", brand="nike"),
            "P2": _filtering("P2", brand="adidas"),
            "P3": _filtering("P3", brand="nike"),
        }
        selected = select_recommendations(
            rows,
            top_k=5,
            config=RecommendationSelectionConfig(max_per_brand=1),
            context=RecommendationSelectionContext(filtering_by_product_id=filtering),
        )
        assert [row.rank for row in selected] == [1, 2]
        assert [row.product_id for row in selected] == ["P1", "P2"]
        assert selected[1].recommendation_score == pytest.approx(0.8)

    def test_top_k_truncation(self) -> None:
        rows = tuple(_ranked(f"P{i}", i, 1.0 - i * 0.01) for i in range(1, 6))
        selected = select_recommendations(rows, top_k=2)
        assert len(selected) == 2

    def test_empty_input(self) -> None:
        assert select_recommendations((), top_k=3) == ()


class TestHardFilters:
    def test_query_filter_constraint(self) -> None:
        rows = (_ranked("P1", 1, 0.9), _ranked("P2", 2, 0.8))
        filtering = {
            "P1": _filtering("P1", brand="nike"),
            "P2": _filtering("P2", brand="adidas"),
        }
        result = select_recommendations_with_diagnostics(
            rows,
            top_k=5,
            context=RecommendationSelectionContext(
                filtering_by_product_id=filtering,
                query_constraints=QueryFilterConstraints(brand="nike"),
            ),
        )
        assert [row.product_id for row in result.selected] == ["P1"]
        assert result.diagnostics[1].reason == RecommendationSelectionRejectionReason.FILTER_CONSTRAINT


class TestDeterminismAndImmutability:
    def test_repeated_selection_identical(self) -> None:
        rows = (_ranked("P1", 1, 0.9), _ranked("P2", 2, 0.8))
        first = select_recommendations(rows, top_k=2)
        second = select_recommendations(rows, top_k=2)
        assert first == second

    def test_input_ranked_rows_unchanged(self) -> None:
        rows = (_ranked("P1", 1, 0.9),)
        snapshot = rows[0].model_dump()
        select_recommendations(rows, top_k=1)
        assert rows[0].model_dump() == snapshot


class TestCombinedConstraints:
    def test_brand_and_product_type_together(self) -> None:
        rows = (
            _ranked("P1", 1, 0.9),
            _ranked("P2", 2, 0.85),
            _ranked("P3", 3, 0.8),
        )
        filtering = {
            "P1": _filtering("P1", brand="nike", product_type="t_shirt"),
            "P2": _filtering("P2", brand="nike", product_type="t_shirt"),
            "P3": _filtering("P3", brand="nike", product_type="dress"),
        }
        selected = select_recommendations(
            rows,
            top_k=5,
            config=RecommendationSelectionConfig(max_per_brand=2, max_per_product_type=1),
            context=RecommendationSelectionContext(filtering_by_product_id=filtering),
        )
        assert [row.product_id for row in selected] == ["P1", "P3"]
