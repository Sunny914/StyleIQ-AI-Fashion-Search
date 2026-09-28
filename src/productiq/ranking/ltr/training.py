"""LightGBM LambdaMART training for ranking (Phase 10.7)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import lightgbm as lgb
from pydantic import BaseModel, ConfigDict

from productiq.ranking.dataset_schema import RankingDataset
from productiq.ranking.ltr.artifact import (
    LTRModelArtifact,
    LTRModelArtifactMetadata,
    save_ltr_model_artifact,
)
from productiq.ranking.ltr.config import LTRTrainingConfig
from productiq.ranking.ltr.feature_matrix import LTRFeatureMatrix, build_feature_matrix_from_dataset
from productiq.ranking.ltr.predict import predict_ltr_scores
from productiq.ranking.ltr.split import QueryGroupSplit, split_ranking_dataset_by_query
from productiq.ranking.ltr.validation import validate_ltr_training_dataset


class LTRTrainingResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    artifact: LTRModelArtifactMetadata
    query_split: QueryGroupSplit
    train_predictions: tuple[float, ...] = ()
    validation_predictions: tuple[float, ...] = ()
    test_predictions: tuple[float, ...] = ()
    artifact_directory: str | None = None


@dataclass(frozen=True)
class _TrainedBoosterBundle:
    booster: lgb.Booster
    metadata: LTRModelArtifactMetadata


def _lightgbm_params(config: LTRTrainingConfig) -> dict[str, object]:
    hp = config.lightgbm
    return {
        "objective": hp.objective,
        "metric": hp.metric,
        "ndcg_eval_at": list(hp.ndcg_eval_at),
        "learning_rate": hp.learning_rate,
        "num_leaves": hp.num_leaves,
        "min_data_in_leaf": hp.min_data_in_leaf,
        "feature_fraction": hp.feature_fraction,
        "bagging_fraction": hp.bagging_fraction,
        "bagging_freq": hp.bagging_freq,
        "lambda_l2": hp.lambda_l2,
        "seed": hp.seed,
        "verbose": -1,
    }


def _train_booster(
    train_matrix: LTRFeatureMatrix,
    valid_matrix: LTRFeatureMatrix,
    *,
    config: LTRTrainingConfig,
) -> lgb.Booster:
    train_set = lgb.Dataset(
        train_matrix.matrix,
        label=train_matrix.labels,
        group=list(train_matrix.group_sizes),
        feature_name=list(train_matrix.feature_spec.feature_names),
        free_raw_data=False,
    )
    valid_set = lgb.Dataset(
        valid_matrix.matrix,
        label=valid_matrix.labels,
        group=list(valid_matrix.group_sizes),
        feature_name=list(valid_matrix.feature_spec.feature_names),
        free_raw_data=False,
    )
    return lgb.train(
        _lightgbm_params(config),
        train_set,
        num_boost_round=config.num_boost_round,
        valid_sets=[valid_set],
        callbacks=[lgb.early_stopping(config.early_stopping_rounds, verbose=False)],
    )


def train_ltr_model(
    dataset: RankingDataset,
    training_config: LTRTrainingConfig | None = None,
    *,
    artifact_directory: Path | None = None,
    benchmark_name: str | None = None,
    benchmark_version: str | None = None,
) -> tuple[LTRTrainingResult, LTRModelArtifact]:
    config = training_config or LTRTrainingConfig()
    validate_ltr_training_dataset(dataset)
    if dataset.metadata.feature_schema_version != config.feature_schema_version:
        msg = "dataset feature_schema_version does not match training config"
        raise ValueError(msg)
    if dataset.metadata.normalization_schema_version != config.normalization_schema_version:
        msg = "dataset normalization_schema_version does not match training config"
        raise ValueError(msg)

    split, (train_ds, val_ds, test_ds) = split_ranking_dataset_by_query(
        dataset,
        config=config.split,
    )
    train_matrix = build_feature_matrix_from_dataset(
        train_ds,
        missing_policy=config.missing_value_policy,
    )
    val_matrix = build_feature_matrix_from_dataset(
        val_ds,
        missing_policy=config.missing_value_policy,
    )
    test_matrix = build_feature_matrix_from_dataset(
        test_ds,
        missing_policy=config.missing_value_policy,
    )
    if train_matrix.labels.shape[0] != train_matrix.row_count:
        msg = "label length must match train row count"
        raise ValueError(msg)
    if sum(train_matrix.group_sizes) != train_matrix.row_count:
        msg = "train group sizes must sum to train row count"
        raise ValueError(msg)

    booster = _train_booster(train_matrix, val_matrix, config=config)
    metadata = LTRModelArtifactMetadata(
        artifact_version=config.artifact_version,
        model_type=config.model_type,
        ltr_version=config.ltr_version,
        dataset_version=config.dataset_version,
        feature_spec=train_matrix.feature_spec,
        training_config=config,
        query_split=split,
        benchmark_name=benchmark_name,
        benchmark_version=benchmark_version,
        query_set_version=dataset.metadata.query_set_version,
        judgment_source_version=dataset.metadata.judgment_source_version,
    )
    artifact = LTRModelArtifact(metadata=metadata, booster=booster)

    saved_path: str | None = None
    if artifact_directory is not None:
        save_ltr_model_artifact(artifact, artifact_directory)
        saved_path = str(artifact_directory)

    train_scores = predict_ltr_scores(artifact, train_matrix)
    val_scores = predict_ltr_scores(artifact, val_matrix)
    test_scores = predict_ltr_scores(artifact, test_matrix)

    result = LTRTrainingResult(
        artifact=metadata,
        query_split=split,
        train_predictions=tuple(float(value) for value in train_scores),
        validation_predictions=tuple(float(value) for value in val_scores),
        test_predictions=tuple(float(value) for value in test_scores),
        artifact_directory=saved_path,
    )
    return result, artifact


__all__ = ["LTRTrainingResult", "train_ltr_model"]
