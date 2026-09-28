"""LTR training configuration (Phase 10.7)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from productiq.ranking.dataset_schema import RANKING_DATASET_VERSION
from productiq.ranking.feature_schema import RANKING_FEATURE_SCHEMA_VERSION
from productiq.ranking.normalization_schema import NORMALIZATION_SCHEMA_VERSION

LTR_MODEL_VERSION = "10.7.0"
LTR_ARTIFACT_VERSION = "10.7.0"
LTR_MISSING_VALUE_POLICY_VERSION = "10.7.0-native-nan"
LTR_MODEL_TYPE = "lightgbm_lambdarank"


class LTRMissingValuePolicy(BaseModel):
    """Explicit missing-value handling for LTR matrices (training == inference)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    policy_version: str = Field(default=LTR_MISSING_VALUE_POLICY_VERSION, min_length=1)
    strategy: Literal["native_nan"] = Field(
        default="native_nan",
        description="Map None to NaN; LightGBM treats NaN as missing during tree learning.",
    )


class LTRQuerySplitConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    split_seed: int = Field(default=42)
    train_query_fraction: float = Field(default=0.6, gt=0.0, lt=1.0)
    validation_query_fraction: float = Field(default=0.2, gt=0.0, lt=1.0)


class LightGBMReferenceHyperparameters(BaseModel):
    """Fixed reference hyperparameters (not tuned in Phase 10.7)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    objective: str = Field(default="lambdarank")
    metric: str = Field(default="ndcg")
    ndcg_eval_at: tuple[int, ...] = (1, 5, 10)
    learning_rate: float = Field(default=0.05, gt=0.0)
    num_leaves: int = Field(default=8, ge=2)
    min_data_in_leaf: int = Field(default=1, ge=1)
    feature_fraction: float = Field(default=1.0, gt=0.0, le=1.0)
    bagging_fraction: float = Field(default=1.0, gt=0.0, le=1.0)
    bagging_freq: int = Field(default=0, ge=0)
    lambda_l2: float = Field(default=1.0, ge=0.0)
    seed: int = Field(default=42)


class LTRTrainingConfig(BaseModel):
    """Immutable reference LTR training configuration."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    ltr_version: str = Field(default=LTR_MODEL_VERSION, min_length=1)
    model_type: str = Field(default=LTR_MODEL_TYPE, min_length=1)
    dataset_version: str = Field(default=RANKING_DATASET_VERSION, min_length=1)
    feature_schema_version: str = Field(default=RANKING_FEATURE_SCHEMA_VERSION, min_length=1)
    normalization_schema_version: str = Field(default=NORMALIZATION_SCHEMA_VERSION, min_length=1)
    missing_value_policy: LTRMissingValuePolicy = Field(default_factory=LTRMissingValuePolicy)
    split: LTRQuerySplitConfig = Field(default_factory=LTRQuerySplitConfig)
    lightgbm: LightGBMReferenceHyperparameters = Field(default_factory=LightGBMReferenceHyperparameters)
    num_boost_round: int = Field(default=50, ge=1)
    early_stopping_rounds: int = Field(default=10, ge=1)
    artifact_version: str = Field(default=LTR_ARTIFACT_VERSION, min_length=1)


__all__ = [
    "LTR_ARTIFACT_VERSION",
    "LTR_MISSING_VALUE_POLICY_VERSION",
    "LTR_MODEL_TYPE",
    "LTR_MODEL_VERSION",
    "LTRMissingValuePolicy",
    "LTRQuerySplitConfig",
    "LTRTrainingConfig",
    "LightGBMReferenceHyperparameters",
]
