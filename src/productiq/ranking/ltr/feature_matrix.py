"""Normalized feature order and matrices for LTR (Phase 10.7)."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from productiq.exceptions.base import RankingError
from productiq.ranking.dataset_schema import RankingDataset, RankingDatasetRow
from productiq.ranking.ltr.config import LTRMissingValuePolicy
from productiq.ranking.normalization_schema import (
    NormalizedCatalogFeatureGroup,
    NormalizedMatchingFeatureGroup,
    NormalizedRankingFeatures,
    NormalizedRetrievalFeatureGroup,
)

LTR_FEATURE_ORDER_VERSION = "10.7.0"


def ordered_normalized_feature_names() -> tuple[str, ...]:
    """Deterministic feature order derived from NormalizedRankingFeatures groups."""
    names: list[str] = []
    for prefix, model in (
        ("retrieval", NormalizedRetrievalFeatureGroup),
        ("matching", NormalizedMatchingFeatureGroup),
        ("catalog", NormalizedCatalogFeatureGroup),
    ):
        for field_name in model.model_fields:
            names.append(f"{prefix}.{field_name}")
    return tuple(names)


ORDERED_LTR_FEATURE_NAMES: tuple[str, ...] = ordered_normalized_feature_names()


def _feature_value(features: NormalizedRankingFeatures, feature_name: str) -> float | None:
    prefix, _, field = feature_name.partition(".")
    if not field:
        msg = f"invalid feature name: {feature_name!r}"
        raise RankingError(msg)
    if prefix == "retrieval":
        value: float | None = getattr(features.retrieval, field)
    elif prefix == "matching":
        value = getattr(features.matching, field)
    elif prefix == "catalog":
        value = getattr(features.catalog, field)
    else:
        msg = f"unknown feature group prefix: {prefix!r}"
        raise RankingError(msg)
    return value


def vectorize_normalized_features(
    features: NormalizedRankingFeatures,
    *,
    feature_names: tuple[str, ...] = ORDERED_LTR_FEATURE_NAMES,
    missing_policy: LTRMissingValuePolicy | None = None,
) -> tuple[float, ...]:
    del missing_policy
    values: list[float] = []
    for name in feature_names:
        raw = _feature_value(features, name)
        if raw is None:
            values.append(float("nan"))
        else:
            if not math.isfinite(raw):
                msg = f"non-finite feature value for {name!r}"
                raise RankingError(msg)
            values.append(raw)
    return tuple(values)


class LTRFeatureSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    feature_order_version: str = Field(default=LTR_FEATURE_ORDER_VERSION, min_length=1)
    feature_schema_version: str = Field(min_length=1)
    normalization_schema_version: str = Field(min_length=1)
    feature_names: tuple[str, ...]
    feature_dimension: int = Field(ge=1)
    missing_value_policy_version: str = Field(min_length=1)


@dataclass(frozen=True)
class LTRFeatureMatrix:
    """Dense numeric matrix aligned with query groups."""

    feature_spec: LTRFeatureSpec
    rows: tuple[RankingDatasetRow, ...]
    matrix: np.ndarray[Any, np.dtype[np.float64]]
    labels: np.ndarray[Any, np.dtype[np.float32]]
    query_ids: tuple[str, ...]
    group_sizes: tuple[int, ...]

    @property
    def row_count(self) -> int:
        return int(self.matrix.shape[0])

    @property
    def feature_count(self) -> int:
        return int(self.matrix.shape[1])


def build_feature_matrix(
    rows: tuple[RankingDatasetRow, ...],
    *,
    feature_names: tuple[str, ...] = ORDERED_LTR_FEATURE_NAMES,
    missing_policy: LTRMissingValuePolicy | None = None,
) -> LTRFeatureMatrix:
    if not rows:
        msg = "cannot build feature matrix from empty rows"
        raise RankingError(msg)
    policy = missing_policy or LTRMissingValuePolicy()
    feature_schema_version = rows[0].feature_schema_version
    normalization_schema_version = rows[0].normalization_schema_version
    for row in rows:
        if row.feature_schema_version != feature_schema_version:
            msg = "inconsistent feature_schema_version in LTR rows"
            raise RankingError(msg)
        if row.normalization_schema_version != normalization_schema_version:
            msg = "inconsistent normalization_schema_version in LTR rows"
            raise RankingError(msg)
    matrix = np.array(
        [
            vectorize_normalized_features(
                row.features,
                feature_names=feature_names,
                missing_policy=policy,
            )
            for row in rows
        ],
        dtype=np.float64,
    )
    labels = np.array([row.relevance_label for row in rows], dtype=np.float32)
    query_ids = tuple(row.query_id for row in rows)
    group_sizes_list: list[int] = []
    if query_ids:
        current = query_ids[0]
        count = 0
        for query_id in query_ids:
            if query_id != current:
                group_sizes_list.append(count)
                current = query_id
                count = 1
            else:
                count += 1
        group_sizes_list.append(count)
    group_sizes = tuple(group_sizes_list)
    if sum(group_sizes) != len(rows):
        msg = "query group sizes must sum to row count"
        raise RankingError(msg)
    spec = LTRFeatureSpec(
        feature_schema_version=feature_schema_version,
        normalization_schema_version=normalization_schema_version,
        feature_names=feature_names,
        feature_dimension=len(feature_names),
        missing_value_policy_version=policy.policy_version,
    )
    return LTRFeatureMatrix(
        feature_spec=spec,
        rows=rows,
        matrix=matrix,
        labels=labels,
        query_ids=query_ids,
        group_sizes=group_sizes,
    )


def build_inference_feature_matrix(
    normalized_features: Sequence[NormalizedRankingFeatures],
    *,
    expected_spec: LTRFeatureSpec,
    missing_policy: LTRMissingValuePolicy | None = None,
) -> LTRFeatureMatrix:
    """Build a prediction matrix aligned with artifact feature_spec (inference-only)."""
    if not normalized_features:
        msg = "cannot build inference feature matrix from empty normalized features"
        raise RankingError(msg)
    policy = missing_policy or LTRMissingValuePolicy()
    if policy.policy_version != expected_spec.missing_value_policy_version:
        msg = "missing_value_policy_version incompatible with LTR artifact feature_spec"
        raise RankingError(msg)
    feature_names = expected_spec.feature_names
    feature_schema_version = normalized_features[0].feature_schema_version
    normalization_schema_version = normalized_features[0].normalization_schema_version
    for row in normalized_features:
        if row.feature_schema_version != feature_schema_version:
            msg = "inconsistent feature_schema_version in inference features"
            raise RankingError(msg)
        if row.normalization_schema_version != normalization_schema_version:
            msg = "inconsistent normalization_schema_version in inference features"
            raise RankingError(msg)
    if feature_schema_version != expected_spec.feature_schema_version:
        msg = "inference feature_schema_version incompatible with LTR artifact"
        raise RankingError(msg)
    if normalization_schema_version != expected_spec.normalization_schema_version:
        msg = "inference normalization_schema_version incompatible with LTR artifact"
        raise RankingError(msg)
    matrix = np.array(
        [
            vectorize_normalized_features(
                row,
                feature_names=feature_names,
                missing_policy=policy,
            )
            for row in normalized_features
        ],
        dtype=np.float64,
    )
    labels = np.zeros(len(normalized_features), dtype=np.float32)
    query_ids = ("inference",) * len(normalized_features)
    spec = expected_spec
    return LTRFeatureMatrix(
        feature_spec=spec,
        rows=(),
        matrix=matrix,
        labels=labels,
        query_ids=query_ids,
        group_sizes=(len(normalized_features),),
    )


def build_feature_matrix_from_dataset(
    dataset: RankingDataset,
    *,
    row_filter: tuple[int, ...] | None = None,
    missing_policy: LTRMissingValuePolicy | None = None,
) -> LTRFeatureMatrix:
    if row_filter is None:
        selected = dataset.rows
    else:
        selected = tuple(dataset.rows[index] for index in row_filter)
    return build_feature_matrix(selected, missing_policy=missing_policy)


__all__ = [
    "LTR_FEATURE_ORDER_VERSION",
    "ORDERED_LTR_FEATURE_NAMES",
    "LTRFeatureMatrix",
    "LTRFeatureSpec",
    "build_feature_matrix",
    "build_feature_matrix_from_dataset",
    "build_inference_feature_matrix",
    "ordered_normalized_feature_names",
    "vectorize_normalized_features",
]
