"""LTR model artifact persistence (Phase 10.7)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import lightgbm as lgb
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from productiq.exceptions.base import RankingError
from productiq.ranking.ltr.config import LTRTrainingConfig
from productiq.ranking.ltr.feature_matrix import LTRFeatureSpec
from productiq.ranking.ltr.split import QueryGroupSplit

LTR_MANIFEST_FILENAME = "ltr_manifest.json"
LTR_MODEL_FILENAME = "model.lgb"


class LTRModelArtifactMetadata(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    artifact_version: str = Field(min_length=1)
    model_type: str = Field(min_length=1)
    ltr_version: str = Field(min_length=1)
    dataset_version: str = Field(min_length=1)
    feature_spec: LTRFeatureSpec
    training_config: LTRTrainingConfig
    query_split: QueryGroupSplit
    benchmark_name: str | None = None
    benchmark_version: str | None = None
    query_set_version: str | None = None
    judgment_source_version: str | None = None


@dataclass(frozen=True)
class LTRModelArtifact:
    metadata: LTRModelArtifactMetadata
    booster: Any


def save_ltr_model_artifact(artifact: LTRModelArtifact, directory: Path) -> Path:
    resolved = Path(directory)
    resolved.mkdir(parents=True, exist_ok=True)
    model_path = resolved / LTR_MODEL_FILENAME
    manifest_path = resolved / LTR_MANIFEST_FILENAME
    artifact.booster.save_model(str(model_path))
    manifest_path.write_text(
        artifact.metadata.model_dump_json(indent=2),
        encoding="utf-8",
    )
    return resolved


def load_ltr_model_artifact(directory: Path) -> LTRModelArtifact:
    resolved = Path(directory)
    if not resolved.is_dir():
        msg = f"LTR artifact directory not found: {resolved}"
        raise RankingError(msg)
    model_path = resolved / LTR_MODEL_FILENAME
    manifest_path = resolved / LTR_MANIFEST_FILENAME
    if not model_path.is_file():
        msg = f"missing LTR model file: {model_path}"
        raise RankingError(msg)
    if not manifest_path.is_file():
        msg = f"missing LTR manifest file: {manifest_path}"
        raise RankingError(msg)
    try:
        metadata = LTRModelArtifactMetadata.model_validate_json(
            manifest_path.read_text(encoding="utf-8"),
        )
    except ValidationError as exc:
        msg = f"LTR manifest is malformed or incompatible: {manifest_path}"
        raise RankingError(msg) from exc
    try:
        booster = lgb.Booster(model_file=str(model_path))
    except Exception as exc:
        msg = f"failed to load LightGBM model from {model_path}"
        raise RankingError(msg) from exc
    return LTRModelArtifact(metadata=metadata, booster=booster)


def load_validated_ltr_artifact(directory: Path) -> LTRModelArtifact:
    """Load artifact and validate compatibility with the current ranking pipeline."""
    from productiq.ranking.ltr.compatibility import validate_ltr_artifact_for_pipeline

    artifact = load_ltr_model_artifact(directory)
    validate_ltr_artifact_for_pipeline(artifact)
    return artifact


def manifest_to_dict(metadata: LTRModelArtifactMetadata) -> dict[str, object]:
    return metadata.model_dump(mode="json")


__all__ = [
    "LTR_MANIFEST_FILENAME",
    "LTR_MODEL_FILENAME",
    "LTRModelArtifact",
    "LTRModelArtifactMetadata",
    "load_ltr_model_artifact",
    "load_validated_ltr_artifact",
    "manifest_to_dict",
    "save_ltr_model_artifact",
]
