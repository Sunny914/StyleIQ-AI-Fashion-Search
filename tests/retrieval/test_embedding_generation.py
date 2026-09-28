"""Tests for Phase 4.11 embedding generation (unit; model smoke optional)."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

from productiq.exceptions.base import SemanticRetrievalError
from productiq.retrieval.embedding_builder import (
    generate_product_embeddings_from_representation_dataset,
    validate_embedding_vectors,
    validate_embeddings_parquet_integrity,
    validate_product_embeddings_parquet,
)
from productiq.retrieval.embedding_encoder import format_bge_query_text, vectors_to_semantic_vector
from productiq.retrieval.embedding_schema import (
    BGE_PRIMARY_MODEL_ID,
    BGE_QUERY_INSTRUCTION,
    EMBEDDING_INPUT_PRODUCT_ID_COLUMN,
    EMBEDDING_INPUT_SEMANTIC_TEXT_COLUMN,
    EXPECTED_CATALOG_PRODUCT_COUNT,
    PRODUCT_EMBEDDINGS_FILENAME,
    PRODUCT_EMBEDDINGS_MANIFEST_FILENAME,
    UNIT_NORM_TOLERANCE,
)
from productiq.retrieval.embedding_selection import load_productiq_embedding_model_selection
from productiq.retrieval.semantic import SemanticSimilarityMetric


def _deterministic_unit_vector(seed: str, dimension: int) -> np.ndarray:
    digest = hashlib.sha256(seed.encode("utf-8")).digest()
    rng = np.random.default_rng(int.from_bytes(digest[:8], "little"))
    raw = rng.standard_normal(dimension).astype(np.float32)
    norm = np.linalg.norm(raw)
    return raw / norm


class FakeDocumentEncoder:
    """Deterministic encoder for pipeline tests (no transformer download)."""

    def __init__(self) -> None:
        self._dimension = 384

    @property
    def embedding_dimension(self) -> int:
        return self._dimension

    @property
    def model_id(self) -> str:
        return BGE_PRIMARY_MODEL_ID

    @property
    def model_revision(self) -> str:
        return "test-revision-deadbeef"

    @property
    def library_version(self) -> str:
        return "0.0-test"

    @property
    def device(self) -> str:
        return "cpu"

    def encode_documents(self, texts: list[str]) -> np.ndarray:
        return np.stack([_deterministic_unit_vector(text, self._dimension) for text in texts])

    def encode_query(self, query_text: str) -> Any:
        prefixed = format_bge_query_text(query_text)
        row = _deterministic_unit_vector(prefixed, self._dimension)
        return vectors_to_semantic_vector(row, expected_dimension=self._dimension)


def _write_mini_representation_parquet(path: Path, rows: list[dict[str, str]]) -> None:
    frame = pd.DataFrame(rows)
    frame.to_parquet(path, engine="pyarrow", index=False)


def test_frozen_model_config_from_selection_artifact() -> None:
    selection = load_productiq_embedding_model_selection(
        Path("resources/embedding/productiq_embedding_model_selection_v1.json")
    )
    assert selection.primary_model.huggingface_model_id == BGE_PRIMARY_MODEL_ID
    assert selection.primary_embedding_dimension == 384
    assert selection.primary_similarity_metric is SemanticSimilarityMetric.COSINE
    assert selection.primary_model.normalize_embeddings is True
    assert selection.primary_model.query_encoding.instruction_prefix == BGE_QUERY_INSTRUCTION


def test_format_bge_query_instruction_applied() -> None:
    formatted = format_bge_query_text("red cotton kurta")
    assert formatted.startswith(BGE_QUERY_INSTRUCTION)
    assert formatted.endswith("red cotton kurta")
    with pytest.raises(SemanticRetrievalError):
        format_bge_query_text("   ")


def test_validate_embedding_vectors_rejects_bad_shapes_and_norms() -> None:
    good = _deterministic_unit_vector("ok", 384).reshape(1, -1)
    validate_embedding_vectors(good, expected_dimension=384)
    with pytest.raises(SemanticRetrievalError):
        validate_embedding_vectors(good.reshape(-1), expected_dimension=384)
    with pytest.raises(SemanticRetrievalError):
        validate_embedding_vectors(good[:, :383], expected_dimension=384)
    bad_norm = np.ones((1, 384), dtype=np.float32) * 2.0
    with pytest.raises(SemanticRetrievalError):
        validate_embedding_vectors(bad_norm, expected_dimension=384)
    nan_row = good.copy()
    nan_row[0, 0] = np.nan
    with pytest.raises(SemanticRetrievalError):
        validate_embedding_vectors(nan_row, expected_dimension=384)


def test_generate_embeddings_pipeline_alignment_and_manifest(tmp_path: Path) -> None:
    source = tmp_path / "product_representations.parquet"
    rows = [
        {EMBEDDING_INPUT_PRODUCT_ID_COLUMN: "p1", EMBEDDING_INPUT_SEMANTIC_TEXT_COLUMN: "alpha dress"},
        {EMBEDDING_INPUT_PRODUCT_ID_COLUMN: "p2", EMBEDDING_INPUT_SEMANTIC_TEXT_COLUMN: "beta shoes"},
    ]
    _write_mini_representation_parquet(source, rows)
    out_parquet = tmp_path / PRODUCT_EMBEDDINGS_FILENAME
    out_manifest = tmp_path / PRODUCT_EMBEDDINGS_MANIFEST_FILENAME
    encoder = FakeDocumentEncoder()
    result = generate_product_embeddings_from_representation_dataset(
        source,
        embeddings_path=out_parquet,
        manifest_path=out_manifest,
        encoder=encoder,
        batch_size=2,
        publish=False,
    )
    assert result.product_count == 2
    assert out_parquet.is_file()
    assert out_manifest.is_file()
    validate_embeddings_parquet_integrity(out_parquet, expected_row_count=2, expected_dimension=384)
    manifest = validate_product_embeddings_parquet(
        out_parquet,
        expected_row_count=2,
        expected_dimension=384,
        manifest_path=out_manifest,
    )
    assert manifest.model_id == BGE_PRIMARY_MODEL_ID
    assert manifest.model_revision == "test-revision-deadbeef"
    assert manifest.embedding_dimension == 384
    assert manifest.query_instruction == BGE_QUERY_INSTRUCTION
    reloaded = pd.read_parquet(out_parquet)
    assert list(reloaded[EMBEDDING_INPUT_PRODUCT_ID_COLUMN]) == ["p1", "p2"]
    assert len(reloaded.iloc[0]["embedding"]) == 384


def test_validate_integrity_detects_duplicate_ids(tmp_path: Path) -> None:
    source = tmp_path / "product_representations.parquet"
    _write_mini_representation_parquet(
        source,
        [
            {EMBEDDING_INPUT_PRODUCT_ID_COLUMN: "dup", EMBEDDING_INPUT_SEMANTIC_TEXT_COLUMN: "a"},
            {EMBEDDING_INPUT_PRODUCT_ID_COLUMN: "dup", EMBEDDING_INPUT_SEMANTIC_TEXT_COLUMN: "b"},
        ],
    )
    with pytest.raises(SemanticRetrievalError, match="duplicate product_id"):
        generate_product_embeddings_from_representation_dataset(
            source,
            encoder=FakeDocumentEncoder(),
            publish=False,
        )


def test_fake_encoder_query_dimension_and_normalization() -> None:
    encoder = FakeDocumentEncoder()
    vector = encoder.encode_query("summer sandals")
    assert len(vector.values) == 384
    norm = np.linalg.norm(np.asarray(vector.values, dtype=np.float32))
    assert norm == pytest.approx(1.0, abs=UNIT_NORM_TOLERANCE)


def test_expected_catalog_count_constant() -> None:
    assert EXPECTED_CATALOG_PRODUCT_COUNT == 367_172


@pytest.mark.skipif(
    not __import__("os").environ.get("PRODUCTIQ_EMBEDDING_SMOKE"),
    reason="Set PRODUCTIQ_EMBEDDING_SMOKE=1 to run local BGE smoke test",
)
def test_bge_encoder_smoke_encode_query() -> None:
    from productiq.retrieval.embedding_encoder import create_bge_small_en_v15_encoder

    encoder = create_bge_small_en_v15_encoder(device="cpu")
    assert encoder.embedding_dimension == 384
    assert encoder.model_id == BGE_PRIMARY_MODEL_ID
    assert len(encoder.model_revision) >= 8
    docs = encoder.encode_documents(["semantic text sample"])
    validate_embedding_vectors(docs, expected_dimension=384)
    query_vec = encoder.encode_query("find blue jeans")
    assert len(query_vec.values) == 384
