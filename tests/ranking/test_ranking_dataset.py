"""Tests for Phase 10.3 ranking dataset construction."""

from __future__ import annotations

import pytest

from productiq.exceptions import RankingError
from productiq.ranking.benchmark_labels import binary_relevance_labels_for_products
from productiq.ranking.dataset_builder import (
    RankingDatasetQueryGroup,
    build_ranking_dataset_from_query_groups,
)
from productiq.ranking.dataset_schema import RankingDatasetRow
from productiq.ranking.dataset_validation import validate_ranking_dataset
from productiq.ranking.feature_schema import RankingFeatures
from productiq.ranking.normalization import normalize_feature_rows
from productiq.retrieval.evaluation.dataset import LexicalEvaluationQuery


def _feature_row(product_id: str) -> RankingFeatures:
    return RankingFeatures(
        product_id=product_id,
        retrieval={
            "bm25_score": 1.0,
            "retrieved_by_bm25": True,
            "retrieved_by_vector": False,
            "retrieved_by_both": False,
        },
        matching={"matched_attribute_count": 0},
        catalog={"discount_price_inr": 100, "original_price_inr": 200, "discount_amount_inr": 100},
    )


def test_build_dataset_preserves_query_grouping() -> None:
    group_a = RankingDatasetQueryGroup(
        query_id="Q1",
        features=(_feature_row("P1"), _feature_row("P2")),
        relevance_label_by_product_id={"P1": 1, "P2": 0},
    )
    group_b = RankingDatasetQueryGroup(
        query_id="Q2",
        features=(_feature_row("P3"),),
        relevance_label_by_product_id={"P3": 1},
    )
    dataset = build_ranking_dataset_from_query_groups(
        (group_a, group_b),
        query_set_version="demo-v1",
        judgment_source_version="manual-v1",
    )
    assert [row.query_id for row in dataset.rows] == ["Q1", "Q1", "Q2"]
    assert dataset.metadata.query_set_version == "demo-v1"


def test_label_separate_from_features() -> None:
    dataset = build_ranking_dataset_from_query_groups(
        (
            RankingDatasetQueryGroup(
                query_id="Q1",
                features=(_feature_row("P1"),),
                relevance_label_by_product_id={"P1": 1},
            ),
        ),
    )
    row = dataset.rows[0]
    assert row.relevance_label == 1
    assert "relevance_label" not in row.features.model_dump()["retrieval"]


def test_duplicate_query_product_rejected() -> None:
    with pytest.raises(RankingError, match="duplicate query/product"):
        build_ranking_dataset_from_query_groups(
            (
                RankingDatasetQueryGroup(
                    query_id="Q1",
                    features=(_feature_row("P1"), _feature_row("P1")),
                ),
            ),
        )


def test_benchmark_label_adapter_uses_judgments_only() -> None:
    evaluation_query = LexicalEvaluationQuery(
        query_id="q_test",
        query_text="nike running",
        category="brand_activity",
        relevant_product_ids=("460946942002", "460825114005"),
    )
    labels = binary_relevance_labels_for_products(
        evaluation_query,
        ["460946942002", "999999999999"],
    )
    assert labels["460946942002"] == 1
    assert labels["999999999999"] == 0


def test_empty_dataset_validates() -> None:
    dataset = build_ranking_dataset_from_query_groups(())
    validate_ranking_dataset(dataset)
    assert dataset.rows == ()


def test_normalized_features_embed_raw_values() -> None:
    raw = _feature_row("P1")
    normalized = normalize_feature_rows((raw,))[0]
    row = RankingDatasetRow(
        query_id="Q1",
        product_id="P1",
        features=normalized,
        relevance_label=1,
    )
    assert row.features.raw.retrieval.bm25_score == pytest.approx(1.0)
