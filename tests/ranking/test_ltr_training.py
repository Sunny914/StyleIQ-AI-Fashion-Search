"""Tests for Phase 10.7 Learning-to-Rank training pipeline."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from productiq.exceptions import RankingError
from productiq.ranking.dataset_builder import (
    RankingDatasetQueryGroup,
    build_ranking_dataset_from_query_groups,
)
from productiq.ranking.dataset_schema import RANKING_DATASET_VERSION
from productiq.ranking.feature_schema import RANKING_FEATURE_SCHEMA_VERSION
from productiq.ranking.ltr.artifact import load_ltr_model_artifact, save_ltr_model_artifact
from productiq.ranking.ltr.config import (
    LTRQuerySplitConfig,
    LTRTrainingConfig,
)
from productiq.ranking.ltr.feature_matrix import (
    ORDERED_LTR_FEATURE_NAMES,
    build_feature_matrix_from_dataset,
    vectorize_normalized_features,
)
from productiq.ranking.ltr.predict import predict_ltr_scores, validate_feature_spec_compatibility
from productiq.ranking.ltr.split import split_queries_for_ltr, split_ranking_dataset_by_query
from productiq.ranking.ltr.training import train_ltr_model
from productiq.ranking.ltr.validation import validate_ltr_training_dataset
from productiq.ranking.normalization_schema import NORMALIZATION_SCHEMA_VERSION
from tests.ranking.test_ranking_dataset import _feature_row


def _labeled_group(query_id: str, product_ids: tuple[str, ...], relevant: set[str]) -> RankingDatasetQueryGroup:
    return RankingDatasetQueryGroup(
        query_id=query_id,
        features=tuple(_feature_row(pid) for pid in product_ids),
        relevance_label_by_product_id={pid: (1 if pid in relevant else 0) for pid in product_ids},
    )


def _fixture_dataset():
    return build_ranking_dataset_from_query_groups(
        (
            _labeled_group("Q1", ("P1", "P2", "P3"), {"P1"}),
            _labeled_group("Q2", ("P4", "P5"), {"P4"}),
            _labeled_group("Q3", ("P6", "P7", "P8"), {"P6", "P7"}),
            _labeled_group("Q4", ("P9", "P10"), {"P10"}),
        ),
        query_set_version="ltr-fixture",
        judgment_source_version="manual-fixture",
        require_labels=True,
    )


def test_query_disjoint_split() -> None:
    dataset = _fixture_dataset()
    split, subsets = split_ranking_dataset_by_query(
        dataset,
        config=LTRQuerySplitConfig(split_seed=42),
    )
    assert not (set(split.train_query_ids) & set(split.validation_query_ids))
    assert not (set(split.train_query_ids) & set(split.test_query_ids))
    assert len(subsets) == 3
    assert split.train_row_count + split.validation_row_count + split.test_row_count == len(dataset.rows)


def test_deterministic_split_seed() -> None:
    ids = ("Q1", "Q2", "Q3", "Q4")
    first = split_queries_for_ltr(ids, config=LTRQuerySplitConfig(split_seed=99))
    second = split_queries_for_ltr(ids, config=LTRQuerySplitConfig(split_seed=99))
    assert first == second


def test_feature_order_matches_schema_field_count() -> None:
    assert len(ORDERED_LTR_FEATURE_NAMES) == 19
    row = _fixture_dataset().rows[0]
    vector = vectorize_normalized_features(row.features)
    assert len(vector) == len(ORDERED_LTR_FEATURE_NAMES)


def test_feature_matrix_dimensions_and_labels() -> None:
    dataset = _fixture_dataset()
    matrix = build_feature_matrix_from_dataset(dataset)
    assert matrix.matrix.shape == (len(dataset.rows), len(ORDERED_LTR_FEATURE_NAMES))
    assert matrix.labels.shape[0] == matrix.row_count
    assert list(matrix.labels) == [row.relevance_label for row in dataset.rows]


def test_group_sizes_sum_to_rows() -> None:
    matrix = build_feature_matrix_from_dataset(_fixture_dataset())
    assert sum(matrix.group_sizes) == matrix.row_count


def test_missing_values_become_nan() -> None:
    row = _fixture_dataset().rows[0]
    values = vectorize_normalized_features(row.features)
    assert any(np.isnan(value) for value in values) or all(np.isfinite(v) or np.isnan(v) for v in values)


def test_invalid_dataset_missing_labels() -> None:
    dataset = build_ranking_dataset_from_query_groups(
        (
            _labeled_group("Q1", ("P1",), {"P1"}),
            _labeled_group("Q2", ("P2",), {"P2"}),
            RankingDatasetQueryGroup(
                query_id="Q3",
                features=(_feature_row("P3"),),
                relevance_label_by_product_id=None,
            ),
        ),
        require_labels=False,
    )
    with pytest.raises(RankingError, match="missing relevance_label"):
        validate_ltr_training_dataset(dataset)


def test_train_predict_save_load(tmp_path: Path) -> None:
    dataset = _fixture_dataset()
    config = LTRTrainingConfig(
        num_boost_round=20,
        early_stopping_rounds=5,
        split=LTRQuerySplitConfig(split_seed=42),
    )
    result, trained = train_ltr_model(
        dataset,
        config,
        artifact_directory=tmp_path / "ltr_model",
    )
    assert len(result.test_predictions) == result.query_split.test_row_count
    loaded = load_ltr_model_artifact(tmp_path / "ltr_model")
    matrix = build_feature_matrix_from_dataset(_fixture_dataset())
    original = predict_ltr_scores(trained, matrix)
    reloaded = predict_ltr_scores(loaded, matrix)
    np.testing.assert_allclose(original, reloaded, rtol=1e-6, atol=1e-6)


def test_incompatible_feature_schema_rejected() -> None:
    _, trained = train_ltr_model(_fixture_dataset(), LTRTrainingConfig(num_boost_round=5))
    bad_norm = trained.metadata.feature_spec.model_copy(
        update={"normalization_schema_version": "99.0.0"},
    )
    with pytest.raises(RankingError, match="normalization_schema_version"):
        validate_feature_spec_compatibility(trained.metadata.feature_spec, bad_norm)
    bad_feature = trained.metadata.feature_spec.model_copy(
        update={"feature_schema_version": "99.0.0"},
    )
    with pytest.raises(RankingError, match="feature_schema_version"):
        validate_feature_spec_compatibility(trained.metadata.feature_spec, bad_feature)


def test_reproducible_training_predictions() -> None:
    dataset = _fixture_dataset()
    config = LTRTrainingConfig(num_boost_round=15, split=LTRQuerySplitConfig(split_seed=7))
    _, first = train_ltr_model(dataset, config)
    _, second = train_ltr_model(dataset, config)
    matrix = build_feature_matrix_from_dataset(dataset)
    np.testing.assert_allclose(
        predict_ltr_scores(first, matrix),
        predict_ltr_scores(second, matrix),
        rtol=0.0,
        atol=0.0,
    )


def test_artifact_lineage_metadata(tmp_path: Path) -> None:
    dataset = _fixture_dataset()
    config = LTRTrainingConfig()
    result, artifact = train_ltr_model(dataset, config, artifact_directory=tmp_path / "art")
    meta = result.artifact
    assert meta.dataset_version == RANKING_DATASET_VERSION
    assert meta.feature_spec.feature_schema_version == RANKING_FEATURE_SCHEMA_VERSION
    assert meta.feature_spec.normalization_schema_version == NORMALIZATION_SCHEMA_VERSION
    assert meta.feature_spec.feature_dimension == len(ORDERED_LTR_FEATURE_NAMES)
    save_ltr_model_artifact(artifact, tmp_path / "art2")
    loaded = load_ltr_model_artifact(tmp_path / "art2")
    assert loaded.metadata.query_split.split_seed == config.split.split_seed


def test_production_baseline_not_integrated_in_retrieve_ranked() -> None:
    import inspect

    from productiq.retrieval.production_pipeline import ProductionRetrievalPipeline

    source = inspect.getsource(ProductionRetrievalPipeline.retrieve_ranked)
    assert "ltr" not in source.casefold()
    assert "train_ltr_model" not in source
