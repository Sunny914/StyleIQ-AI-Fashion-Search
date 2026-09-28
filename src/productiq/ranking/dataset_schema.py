"""Ranking dataset schema (Phase 10.3)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from productiq.ranking.feature_schema import RANKING_FEATURE_SCHEMA_VERSION
from productiq.ranking.normalization_schema import (
    NORMALIZATION_SCHEMA_VERSION,
    NormalizedRankingFeatures,
)

RANKING_DATASET_VERSION = "10.3.0"


class RankingDatasetRow(BaseModel):
    """One query × product training/inference row (features separate from label)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    query_id: str = Field(min_length=1)
    product_id: str = Field(min_length=1)
    features: NormalizedRankingFeatures
    relevance_label: int | None = Field(
        default=None,
        ge=0,
        le=1,
        description="Binary judged relevance (y); not part of the feature vector.",
    )
    feature_schema_version: str = Field(default=RANKING_FEATURE_SCHEMA_VERSION, min_length=1)
    normalization_schema_version: str = Field(default=NORMALIZATION_SCHEMA_VERSION, min_length=1)

    @model_validator(mode="after")
    def validate_row_consistency(self) -> RankingDatasetRow:
        if self.product_id != self.features.product_id:
            msg = "row product_id must match features.product_id"
            raise ValueError(msg)
        if self.feature_schema_version != self.features.feature_schema_version:
            msg = "row feature_schema_version must match embedded features"
            raise ValueError(msg)
        if self.normalization_schema_version != self.features.normalization_schema_version:
            msg = "row normalization_schema_version must match embedded features"
            raise ValueError(msg)
        return self


class RankingDatasetMetadata(BaseModel):
    """Reproducibility metadata for a ranking dataset artifact."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    dataset_version: str = Field(default=RANKING_DATASET_VERSION, min_length=1)
    feature_schema_version: str = Field(default=RANKING_FEATURE_SCHEMA_VERSION, min_length=1)
    normalization_schema_version: str = Field(default=NORMALIZATION_SCHEMA_VERSION, min_length=1)
    query_set_version: str | None = Field(default=None, min_length=1)
    judgment_source_version: str | None = Field(default=None, min_length=1)


class RankingDataset(BaseModel):
    """Grouped ranking dataset preserving query identity on each row."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    metadata: RankingDatasetMetadata
    rows: tuple[RankingDatasetRow, ...] = ()


def ranking_dataset_to_dict(dataset: RankingDataset) -> dict[str, Any]:
    return dataset.model_dump(mode="json")


__all__ = [
    "RANKING_DATASET_VERSION",
    "RankingDataset",
    "RankingDatasetMetadata",
    "RankingDatasetRow",
    "ranking_dataset_to_dict",
]
