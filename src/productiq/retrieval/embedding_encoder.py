"""Local BGE embedding encoder (Phase 4.11)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Protocol, cast, runtime_checkable

import numpy as np
from numpy.typing import NDArray

from productiq.exceptions.base import SemanticRetrievalError
from productiq.retrieval.embedding_device import resolve_embedding_device
from productiq.retrieval.embedding_schema import (
    BGE_PRIMARY_MODEL_ID,
    BGE_QUERY_INSTRUCTION,
)
from productiq.retrieval.embedding_selection import load_productiq_embedding_model_selection
from productiq.retrieval.semantic import SemanticVector


@runtime_checkable
class DocumentEmbeddingEncoder(Protocol):
    """Encode product semantic documents into normalized vectors."""

    @property
    def embedding_dimension(self) -> int: ...

    @property
    def model_id(self) -> str: ...

    @property
    def model_revision(self) -> str: ...

    @property
    def library_version(self) -> str: ...

    @property
    def device(self) -> str: ...

    def encode_documents(self, texts: list[str]) -> NDArray[np.float32]: ...

    def encode_query(self, query_text: str) -> SemanticVector: ...


def _normalize_semantic_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    return str(value)


def format_bge_query_text(query_text: str) -> str:
    """Apply frozen BGE short-query retrieval instruction (query side only)."""
    stripped = query_text.strip()
    if not stripped:
        msg = "query text must not be empty for query embedding"
        raise SemanticRetrievalError(msg)
    return f"{BGE_QUERY_INSTRUCTION}{stripped}"


def vectors_to_semantic_vector(row: NDArray[np.float32], *, expected_dimension: int) -> SemanticVector:
    if row.ndim != 1:
        msg = "embedding row must be one-dimensional"
        raise SemanticRetrievalError(msg)
    if row.shape[0] != expected_dimension:
        msg = f"embedding dimension must be {expected_dimension}"
        raise SemanticRetrievalError(msg)
    if not np.all(np.isfinite(row)):
        msg = "embedding contains non-finite values"
        raise SemanticRetrievalError(msg)
    return SemanticVector(values=tuple(float(value) for value in row))


@dataclass
class SentenceTransformerBGEEncoder:
    """Local ``sentence-transformers`` encoder for ``BAAI/bge-small-en-v1.5``."""

    _model: object
    _model_id: str
    _model_revision: str
    _embedding_dimension: int
    _device: str
    _library_version: str
    _encode_batch_size: int

    @property
    def embedding_dimension(self) -> int:
        return self._embedding_dimension

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def model_revision(self) -> str:
        return self._model_revision

    @property
    def library_version(self) -> str:
        return self._library_version

    @property
    def device(self) -> str:
        return self._device

    def encode_documents(self, texts: list[str]) -> NDArray[np.float32]:
        normalized = [_normalize_semantic_text(text) for text in texts]
        return self._encode(normalized)

    def encode_query(self, query_text: str) -> SemanticVector:
        encoded = self._encode([format_bge_query_text(query_text)])
        return vectors_to_semantic_vector(encoded[0], expected_dimension=self._embedding_dimension)

    def _encode(self, texts: list[str]) -> NDArray[np.float32]:
        encode = cast(Any, self._model).encode
        vectors = encode(
            texts,
            batch_size=min(len(texts), self._encode_batch_size) if texts else 1,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        array = np.asarray(vectors, dtype=np.float32)
        if array.ndim == 1:
            array = array.reshape(1, -1)
        if array.shape[1] != self._embedding_dimension:
            msg = f"model returned dimension {array.shape[1]}, expected {self._embedding_dimension}"
            raise SemanticRetrievalError(msg)
        return array


def create_bge_small_en_v15_encoder(
    *,
    device: str | None = None,
    torch_device: str | None = None,
    model_revision: str | None = None,
    encode_batch_size: int = 64,
    allow_cpu_fallback: bool = False,
) -> SentenceTransformerBGEEncoder:
    """Download and load the frozen primary BGE model for local inference."""
    selection = load_productiq_embedding_model_selection()
    expected_dim = selection.primary_embedding_dimension
    if torch_device is not None:
        resolved_device = torch_device
    else:
        resolved_device = resolve_embedding_device(device, allow_cpu_fallback=allow_cpu_fallback).selected
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        msg = "sentence-transformers is required for embedding generation (Phase 4.11)"
        raise SemanticRetrievalError(msg) from exc

    import sentence_transformers

    revision = model_revision
    model_kwargs: dict[str, str] = {}
    if revision:
        model_kwargs["revision"] = revision
    model = SentenceTransformer(BGE_PRIMARY_MODEL_ID, device=resolved_device, model_kwargs=model_kwargs)
    resolved_revision = revision or _resolve_model_revision(BGE_PRIMARY_MODEL_ID)
    dimension_value = model.get_sentence_embedding_dimension()
    if dimension_value is None:
        msg = "loaded model did not report sentence embedding dimension"
        raise SemanticRetrievalError(msg)
    dimension = int(dimension_value)
    if dimension != expected_dim:
        msg = f"loaded model dimension {dimension} != expected {expected_dim}"
        raise SemanticRetrievalError(msg)
    reported_device = str(getattr(model, "device", resolved_device))
    return SentenceTransformerBGEEncoder(
        _model=model,
        _model_id=BGE_PRIMARY_MODEL_ID,
        _model_revision=resolved_revision,
        _embedding_dimension=dimension,
        _device=reported_device,
        _library_version=str(getattr(sentence_transformers, "__version__", "unknown")),
        _encode_batch_size=encode_batch_size,
    )


def _resolve_model_revision(model_id: str) -> str:
    try:
        from huggingface_hub import model_info
    except ImportError:
        return "unknown"
    try:
        info = model_info(model_id)
        return str(info.sha)
    except (OSError, RuntimeError, ValueError):
        return "unknown"


__all__ = [
    "DocumentEmbeddingEncoder",
    "SentenceTransformerBGEEncoder",
    "create_bge_small_en_v15_encoder",
    "format_bge_query_text",
    "vectors_to_semantic_vector",
]
