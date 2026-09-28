"""Checkpoint/resume metadata for long Phase 4.11 embedding generation runs."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from productiq.exceptions.base import SemanticRetrievalError
from productiq.retrieval.embedding_schema import (
    BGE_PRIMARY_MODEL_ID,
    DOCUMENT_ENCODING_RULE,
    NORMALIZATION_L2,
)

CHECKPOINT_VERSION = "1.0.0"
CHECKPOINT_FILENAME = "checkpoint.json"
CHUNKS_SUBDIR_NAME = "chunks"
DEFAULT_EMBEDDING_CHUNK_SIZE = 10_000
EMBEDDING_GENERATION_STATE_DIRNAME = ".embedding_generation"


class EmbeddingGenerationCheckpoint(BaseModel):
    """On-disk checkpoint for resumable embedding generation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    checkpoint_version: str = CHECKPOINT_VERSION
    status: Literal["in_progress", "complete"] = "in_progress"
    source_representation_checksum: str
    source_representation_row_count: int = Field(ge=0)
    target_product_count: int = Field(ge=0)
    model_id: str
    model_revision: str
    embedding_dimension: int = Field(gt=0)
    normalization_method: str
    document_encoding_rule: str
    batch_size: int = Field(gt=0)
    device: str
    chunk_size: int = Field(gt=0)
    completed_product_count: int = Field(ge=0)
    last_product_id: str | None = None
    chunk_file_count: int = Field(ge=0)
    updated_at_utc: str


@dataclass(frozen=True)
class EmbeddingRunConfiguration:
    source_representation_checksum: str
    source_representation_row_count: int
    target_product_count: int
    model_id: str
    model_revision: str
    embedding_dimension: int
    normalization_method: str
    document_encoding_rule: str
    batch_size: int
    device: str
    chunk_size: int


def default_checkpoint_dir(processed_dir: Path) -> Path:
    return processed_dir / EMBEDDING_GENERATION_STATE_DIRNAME


def checkpoint_path(checkpoint_dir: Path) -> Path:
    return checkpoint_dir / CHECKPOINT_FILENAME


def chunks_dir(checkpoint_dir: Path) -> Path:
    return checkpoint_dir / CHUNKS_SUBDIR_NAME


def chunk_file_path(checkpoint_dir: Path, chunk_index: int) -> Path:
    return chunks_dir(checkpoint_dir) / f"chunk_{chunk_index:06d}.parquet"


def load_checkpoint(path: Path) -> EmbeddingGenerationCheckpoint:
    resolved = Path(path)
    if not resolved.is_file():
        msg = f"embedding checkpoint not found: {resolved}"
        raise SemanticRetrievalError(msg)
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        msg = f"embedding checkpoint is not valid JSON: {resolved}"
        raise SemanticRetrievalError(msg) from exc
    if not isinstance(payload, dict):
        msg = "embedding checkpoint must be a JSON object"
        raise SemanticRetrievalError(msg)
    return EmbeddingGenerationCheckpoint.model_validate(payload)


def save_checkpoint(path: Path, checkpoint: EmbeddingGenerationCheckpoint) -> None:
    resolved = Path(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    payload = checkpoint.model_dump()
    temp_path = resolved.with_suffix(".json.tmp")
    temp_path.write_text(f"{json.dumps(payload, indent=2, sort_keys=True)}\n", encoding="utf-8")
    os.replace(temp_path, resolved)


def build_run_configuration(
    *,
    source_manifest: dict[str, Any] | None,
    target_product_count: int,
    model_id: str,
    model_revision: str,
    embedding_dimension: int,
    batch_size: int,
    device: str,
    chunk_size: int = DEFAULT_EMBEDDING_CHUNK_SIZE,
) -> EmbeddingRunConfiguration:
    checksum = str(source_manifest.get("checksum", "")) if source_manifest else ""
    if not checksum:
        msg = "source representation manifest checksum is required for checkpointed generation"
        raise SemanticRetrievalError(msg)
    row_count = int(source_manifest.get("row_count", 0)) if source_manifest else 0
    return EmbeddingRunConfiguration(
        source_representation_checksum=checksum,
        source_representation_row_count=row_count,
        target_product_count=target_product_count,
        model_id=model_id,
        model_revision=model_revision,
        embedding_dimension=embedding_dimension,
        normalization_method=NORMALIZATION_L2,
        document_encoding_rule=DOCUMENT_ENCODING_RULE,
        batch_size=batch_size,
        device=device,
        chunk_size=chunk_size,
    )


def configuration_to_checkpoint_fields(config: EmbeddingRunConfiguration) -> dict[str, Any]:
    return {
        "source_representation_checksum": config.source_representation_checksum,
        "source_representation_row_count": config.source_representation_row_count,
        "target_product_count": config.target_product_count,
        "model_id": config.model_id,
        "model_revision": config.model_revision,
        "embedding_dimension": config.embedding_dimension,
        "normalization_method": config.normalization_method,
        "document_encoding_rule": config.document_encoding_rule,
        "batch_size": config.batch_size,
        "device": config.device,
        "chunk_size": config.chunk_size,
    }


def assert_checkpoint_compatible(
    checkpoint: EmbeddingGenerationCheckpoint,
    config: EmbeddingRunConfiguration,
) -> None:
    expected = configuration_to_checkpoint_fields(config)
    mismatches: list[str] = []
    for key, expected_value in expected.items():
        actual_value = getattr(checkpoint, key)
        if actual_value != expected_value:
            mismatches.append(f"{key}: checkpoint={actual_value!r} current={expected_value!r}")
    if checkpoint.checkpoint_version != CHECKPOINT_VERSION:
        mismatches.append(
            f"checkpoint_version: checkpoint={checkpoint.checkpoint_version!r} "
            f"current={CHECKPOINT_VERSION!r}"
        )
    if checkpoint.model_id != BGE_PRIMARY_MODEL_ID:
        mismatches.append(f"unexpected checkpoint model_id {checkpoint.model_id!r}")
    if mismatches:
        detail = "; ".join(mismatches)
        msg = f"refusing to resume embedding generation due to incompatible checkpoint: {detail}"
        raise SemanticRetrievalError(msg)


def new_checkpoint(
    config: EmbeddingRunConfiguration,
    *,
    completed_product_count: int = 0,
    last_product_id: str | None = None,
    chunk_file_count: int = 0,
    status: Literal["in_progress", "complete"] = "in_progress",
) -> EmbeddingGenerationCheckpoint:
    fields = configuration_to_checkpoint_fields(config)
    return EmbeddingGenerationCheckpoint(
        status=status,
        completed_product_count=completed_product_count,
        last_product_id=last_product_id,
        chunk_file_count=chunk_file_count,
        updated_at_utc=datetime.now(tz=UTC).isoformat(),
        **fields,
    )


def list_chunk_files(checkpoint_dir: Path) -> list[Path]:
    directory = chunks_dir(checkpoint_dir)
    if not directory.is_dir():
        return []
    return sorted(directory.glob("chunk_*.parquet"))


__all__ = [
    "CHECKPOINT_FILENAME",
    "CHECKPOINT_VERSION",
    "CHUNKS_SUBDIR_NAME",
    "DEFAULT_EMBEDDING_CHUNK_SIZE",
    "EMBEDDING_GENERATION_STATE_DIRNAME",
    "EmbeddingGenerationCheckpoint",
    "EmbeddingRunConfiguration",
    "assert_checkpoint_compatible",
    "build_run_configuration",
    "checkpoint_path",
    "chunk_file_path",
    "chunks_dir",
    "default_checkpoint_dir",
    "list_chunk_files",
    "load_checkpoint",
    "new_checkpoint",
    "save_checkpoint",
]
