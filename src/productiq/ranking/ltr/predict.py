"""LTR model prediction with schema compatibility checks (Phase 10.7)."""

from __future__ import annotations

from typing import Any

import numpy as np

from productiq.exceptions.base import RankingError
from productiq.ranking.ltr.artifact import LTRModelArtifact
from productiq.ranking.ltr.feature_matrix import LTRFeatureMatrix, LTRFeatureSpec


def validate_feature_spec_compatibility(
    expected: LTRFeatureSpec,
    actual: LTRFeatureSpec,
) -> None:
    if expected.feature_schema_version != actual.feature_schema_version:
        msg = "feature_schema_version incompatible with LTR artifact"
        raise RankingError(msg)
    if expected.normalization_schema_version != actual.normalization_schema_version:
        msg = "normalization_schema_version incompatible with LTR artifact"
        raise RankingError(msg)
    if expected.feature_names != actual.feature_names:
        msg = "feature name order incompatible with LTR artifact"
        raise RankingError(msg)
    if expected.feature_dimension != actual.feature_dimension:
        msg = "feature dimension incompatible with LTR artifact"
        raise RankingError(msg)
    if expected.missing_value_policy_version != actual.missing_value_policy_version:
        msg = "missing_value_policy_version incompatible with LTR artifact"
        raise RankingError(msg)


def predict_ltr_scores(
    artifact: LTRModelArtifact,
    feature_matrix: LTRFeatureMatrix,
) -> np.ndarray[Any, np.dtype[np.float64]]:
    validate_feature_spec_compatibility(
        artifact.metadata.feature_spec,
        feature_matrix.feature_spec,
    )
    if feature_matrix.matrix.shape[1] != artifact.metadata.feature_spec.feature_dimension:
        msg = "feature matrix column count does not match artifact"
        raise RankingError(msg)
    scores = artifact.booster.predict(feature_matrix.matrix)
    return np.asarray(scores, dtype=np.float64)


__all__ = ["predict_ltr_scores", "validate_feature_spec_compatibility"]
