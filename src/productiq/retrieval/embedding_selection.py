"""Frozen embedding model selection contract (Phase 4.10 — no inference)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from productiq.exceptions.base import SemanticRetrievalError
from productiq.retrieval.semantic import SemanticSimilarityMetric

EMBEDDING_MODEL_SELECTION_FILENAME = "productiq_embedding_model_selection_v1.json"
EMBEDDING_MODEL_SELECTION_VERSION = "1.0.0"
PRODUCTIQ_CATALOG_PRODUCT_COUNT = 367_172


class EmbeddingTextEncodingContract(BaseModel):
    """Query vs document prefix/instruction rules for asymmetric retrieval."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    instruction_prefix: str = ""
    apply_instruction_to: str = Field(min_length=1)
    source_field: str | None = None
    notes: str | None = None


class EmbeddingModelSpec(BaseModel):
    """One frozen embedding model entry (primary or fallback)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    role: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    huggingface_model_id: str = Field(min_length=1)
    model_revision: str | None = None
    architecture: str = Field(min_length=1)
    parameter_count_approx: str = Field(min_length=1)
    embedding_dimension: int = Field(gt=0)
    max_input_tokens: int = Field(gt=0)
    license: str = Field(min_length=1)
    model_card_url: str = Field(min_length=1)
    normalize_embeddings: bool = True
    pooling: str | None = None
    query_encoding: EmbeddingTextEncodingContract
    document_encoding: EmbeddingTextEncodingContract
    selection_rationale_summary: str | None = None
    fallback_rationale_summary: str | None = None

    @field_validator("huggingface_model_id")
    @classmethod
    def strip_model_id(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            msg = "huggingface_model_id must not be empty"
            raise ValueError(msg)
        return stripped


class RawVectorStorageEstimate(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    formula: str
    dimension_384_mb: float
    dimension_384_gib: float
    dimension_768_mb: float
    dimension_768_gib: float
    dimension_1024_mb: float
    dimension_1024_gib: float
    notes: str = Field(min_length=1)


class ProductIQEmbeddingModelSelection(BaseModel):
    """Versioned ProductIQ embedding model selection artifact."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    selection_name: str = Field(min_length=1)
    selection_version: str = Field(min_length=1)
    selection_date: str = Field(min_length=1)
    productiq_context: dict[str, Any]
    primary_model: EmbeddingModelSpec
    fallback_model: EmbeddingModelSpec
    storage_raw_float32_bytes_per_product: RawVectorStorageEstimate
    phase_4_11_dependencies_note: str = Field(min_length=1)
    limitations: tuple[str, ...]

    @property
    def primary_similarity_metric(self) -> SemanticSimilarityMetric:
        return SemanticSimilarityMetric.COSINE

    @property
    def primary_embedding_dimension(self) -> int:
        return self.primary_model.embedding_dimension


def default_embedding_selection_path(repo_root: Path | None = None) -> Path:
    root = repo_root or Path.cwd()
    return root / "resources" / "embedding" / EMBEDDING_MODEL_SELECTION_FILENAME


def load_productiq_embedding_model_selection(
    path: Path | None = None,
) -> ProductIQEmbeddingModelSelection:
    """Load the frozen Phase 4.10 embedding model selection JSON."""
    resolved = path or default_embedding_selection_path()
    if not resolved.is_file():
        msg = f"embedding model selection artifact not found: {resolved}"
        raise SemanticRetrievalError(msg)
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        msg = f"embedding model selection artifact is not valid JSON: {resolved}"
        raise SemanticRetrievalError(msg) from exc
    if not isinstance(payload, dict):
        msg = "embedding model selection artifact must be a JSON object"
        raise SemanticRetrievalError(msg)
    return ProductIQEmbeddingModelSelection.model_validate(payload)


def raw_float32_vector_storage_bytes(product_count: int, embedding_dimension: int) -> int:
    """Raw float32 payload bytes for ``product_count`` vectors (no DB/index overhead)."""
    if product_count < 0 or embedding_dimension <= 0:
        msg = "product_count must be non-negative and embedding_dimension positive"
        raise SemanticRetrievalError(msg)
    return product_count * embedding_dimension * 4


__all__ = [
    "EMBEDDING_MODEL_SELECTION_FILENAME",
    "EMBEDDING_MODEL_SELECTION_VERSION",
    "PRODUCTIQ_CATALOG_PRODUCT_COUNT",
    "EmbeddingModelSpec",
    "EmbeddingTextEncodingContract",
    "ProductIQEmbeddingModelSelection",
    "RawVectorStorageEstimate",
    "default_embedding_selection_path",
    "load_productiq_embedding_model_selection",
    "raw_float32_vector_storage_bytes",
]
