"""LTR artifact compatibility with the ranking pipeline (Phase 10.8)."""

from __future__ import annotations

from pydantic import ValidationError

from productiq.exceptions.base import RankingError
from productiq.ranking.feature_schema import RANKING_FEATURE_SCHEMA_VERSION
from productiq.ranking.ltr.artifact import LTRModelArtifact
from productiq.ranking.ltr.config import (
    LTR_MISSING_VALUE_POLICY_VERSION,
    LTRMissingValuePolicy,
)
from productiq.ranking.ltr.feature_matrix import (
    LTR_FEATURE_ORDER_VERSION,
    ORDERED_LTR_FEATURE_NAMES,
)

_EXPECTED_MISSING_POLICY = LTRMissingValuePolicy()


def validate_ltr_artifact_for_pipeline(artifact: LTRModelArtifact) -> None:
    """Ensure a loaded artifact matches current feature/normalization/LTR contracts."""
    metadata = artifact.metadata
    spec = metadata.feature_spec
    training = metadata.training_config

    if spec.feature_schema_version != RANKING_FEATURE_SCHEMA_VERSION:
        msg = (
            "LTR artifact feature_schema_version incompatible with pipeline "
            f"(expected {RANKING_FEATURE_SCHEMA_VERSION!r}, got {spec.feature_schema_version!r})"
        )
        raise RankingError(msg)
    if training.feature_schema_version != RANKING_FEATURE_SCHEMA_VERSION:
        msg = "LTR training_config feature_schema_version inconsistent with pipeline"
        raise RankingError(msg)

    from productiq.ranking.normalization_schema import NORMALIZATION_SCHEMA_VERSION

    if spec.normalization_schema_version != NORMALIZATION_SCHEMA_VERSION:
        msg = (
            "LTR artifact normalization_schema_version incompatible with pipeline "
            f"(expected {NORMALIZATION_SCHEMA_VERSION!r}, "
            f"got {spec.normalization_schema_version!r})"
        )
        raise RankingError(msg)
    if training.normalization_schema_version != NORMALIZATION_SCHEMA_VERSION:
        msg = "LTR training_config normalization_schema_version inconsistent with pipeline"
        raise RankingError(msg)

    if spec.feature_order_version != LTR_FEATURE_ORDER_VERSION:
        msg = (
            "LTR feature_order_version incompatible with pipeline "
            f"(expected {LTR_FEATURE_ORDER_VERSION!r}, got {spec.feature_order_version!r})"
        )
        raise RankingError(msg)

    if spec.missing_value_policy_version != LTR_MISSING_VALUE_POLICY_VERSION:
        msg = (
            "LTR missing_value_policy_version incompatible with pipeline "
            f"(expected {LTR_MISSING_VALUE_POLICY_VERSION!r}, "
            f"got {spec.missing_value_policy_version!r})"
        )
        raise RankingError(msg)
    if training.missing_value_policy.policy_version != LTR_MISSING_VALUE_POLICY_VERSION:
        msg = "LTR training_config missing_value_policy inconsistent with pipeline"
        raise RankingError(msg)
    if training.missing_value_policy.strategy != _EXPECTED_MISSING_POLICY.strategy:
        msg = "LTR training_config missing_value strategy must be native_nan"
        raise RankingError(msg)

    if spec.feature_names != ORDERED_LTR_FEATURE_NAMES:
        msg = "LTR artifact feature_names must match ORDERED_LTR_FEATURE_NAMES exactly"
        raise RankingError(msg)
    if spec.feature_dimension != len(ORDERED_LTR_FEATURE_NAMES):
        msg = "LTR artifact feature_dimension inconsistent with ORDERED_LTR_FEATURE_NAMES"
        raise RankingError(msg)
    if len(spec.feature_names) != spec.feature_dimension:
        msg = "LTR artifact feature_spec feature_dimension inconsistent with feature_names length"
        raise RankingError(msg)

    if training.model_type != metadata.model_type:
        msg = "LTR artifact model_type inconsistent with training_config"
        raise RankingError(msg)
    if training.ltr_version != metadata.ltr_version:
        msg = "LTR artifact ltr_version inconsistent with training_config"
        raise RankingError(msg)

    booster_features = artifact.booster.num_feature()
    if booster_features != spec.feature_dimension:
        msg = (
            "LightGBM model feature count does not match artifact feature_dimension "
            f"(model={booster_features}, spec={spec.feature_dimension})"
        )
        raise RankingError(msg)


def validate_ltr_manifest_json(raw: str) -> None:
    """Raise RankingError when manifest JSON is malformed."""
    from productiq.ranking.ltr.artifact import LTRModelArtifactMetadata

    try:
        LTRModelArtifactMetadata.model_validate_json(raw)
    except ValidationError as exc:
        msg = "LTR manifest JSON is malformed or incompatible"
        raise RankingError(msg) from exc


__all__ = ["validate_ltr_artifact_for_pipeline", "validate_ltr_manifest_json"]
