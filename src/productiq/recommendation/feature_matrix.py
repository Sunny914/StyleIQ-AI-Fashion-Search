"""Dense feature matrices for future recommendation LTR (Phase 11.4)."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from productiq.exceptions.base import RecommendationError
from productiq.ranking.ltr.config import LTRMissingValuePolicy
from productiq.recommendation.feature_schema import (
    ORDERED_RECOMMENDATION_FEATURE_NAMES,
    RECOMMENDATION_FEATURE_ORDER_VERSION,
    RecommendationFeatures,
)


def _feature_value(features: RecommendationFeatures, feature_name: str) -> bool | int | float | None:
    prefix, _, field = feature_name.partition(".")
    if not field:
        msg = f"invalid feature name: {feature_name!r}"
        raise RecommendationError(msg)
    if prefix == "generation":
        value: bool | int | float | None = getattr(features.generation, field)
    elif prefix == "similarity":
        value = getattr(features.similarity, field)
    elif prefix == "structured":
        value = getattr(features.structured, field)
    elif prefix == "catalog":
        value = getattr(features.catalog, field)
    else:
        msg = f"unknown feature group prefix: {prefix!r}"
        raise RecommendationError(msg)
    return value


def _scalar_for_matrix(raw: bool | float | None) -> float:
    if raw is None:
        return float("nan")
    if isinstance(raw, bool):
        return 1.0 if raw else 0.0
    if isinstance(raw, int):
        return float(raw)
    if not math.isfinite(raw):
        msg = "non-finite numeric feature value"
        raise RecommendationError(msg)
    return raw


def vectorize_recommendation_features(
    features: RecommendationFeatures,
    *,
    feature_names: tuple[str, ...] = ORDERED_RECOMMENDATION_FEATURE_NAMES,
    missing_policy: LTRMissingValuePolicy | None = None,
) -> tuple[float, ...]:
    """Flatten features to floats; ``None`` becomes NaN at the matrix boundary only."""
    del missing_policy
    return tuple(_scalar_for_matrix(_feature_value(features, name)) for name in feature_names)


class RecommendationFeatureSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    feature_order_version: str = Field(default=RECOMMENDATION_FEATURE_ORDER_VERSION, min_length=1)
    feature_schema_version: str = Field(min_length=1)
    feature_names: tuple[str, ...]
    feature_dimension: int = Field(ge=1)
    missing_value_policy_version: str = Field(min_length=1)


@dataclass(frozen=True)
class RecommendationFeatureMatrix:
    """Dense numeric matrix aligned with candidate feature rows."""

    feature_spec: RecommendationFeatureSpec
    features: tuple[RecommendationFeatures, ...]
    matrix: np.ndarray[Any, np.dtype[np.float64]]
    product_ids: tuple[str, ...]

    @property
    def row_count(self) -> int:
        return int(self.matrix.shape[0])

    @property
    def feature_count(self) -> int:
        return int(self.matrix.shape[1])


def build_recommendation_feature_matrix(
    rows: Sequence[RecommendationFeatures],
    *,
    feature_names: tuple[str, ...] = ORDERED_RECOMMENDATION_FEATURE_NAMES,
    missing_policy: LTRMissingValuePolicy | None = None,
) -> RecommendationFeatureMatrix:
    if not rows:
        msg = "cannot build recommendation feature matrix from empty rows"
        raise RecommendationError(msg)
    policy = missing_policy or LTRMissingValuePolicy()
    feature_schema_version = rows[0].feature_schema_version
    for row in rows:
        if row.feature_schema_version != feature_schema_version:
            msg = "inconsistent feature_schema_version across recommendation feature rows"
            raise RecommendationError(msg)
    matrix = np.array(
        [
            vectorize_recommendation_features(
                row,
                feature_names=feature_names,
                missing_policy=policy,
            )
            for row in rows
        ],
        dtype=np.float64,
    )
    spec = RecommendationFeatureSpec(
        feature_schema_version=feature_schema_version,
        feature_names=feature_names,
        feature_dimension=len(feature_names),
        missing_value_policy_version=policy.policy_version,
    )
    product_ids = tuple(row.product_id for row in rows)
    return RecommendationFeatureMatrix(
        feature_spec=spec,
        features=tuple(rows),
        matrix=matrix,
        product_ids=product_ids,
    )


__all__ = [
    "ORDERED_RECOMMENDATION_FEATURE_NAMES",
    "RECOMMENDATION_FEATURE_ORDER_VERSION",
    "RecommendationFeatureMatrix",
    "RecommendationFeatureSpec",
    "build_recommendation_feature_matrix",
    "vectorize_recommendation_features",
]
