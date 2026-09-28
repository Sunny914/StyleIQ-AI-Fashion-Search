"""Tests for Phase 4.10 embedding model selection contract."""

from __future__ import annotations

from pathlib import Path

import pytest

from productiq.retrieval.embedding_selection import (
    EMBEDDING_MODEL_SELECTION_VERSION,
    PRODUCTIQ_CATALOG_PRODUCT_COUNT,
    load_productiq_embedding_model_selection,
    raw_float32_vector_storage_bytes,
)
from productiq.retrieval.semantic import SemanticSimilarityMetric


def test_load_frozen_selection_artifact() -> None:
    selection = load_productiq_embedding_model_selection(
        Path("resources/embedding/productiq_embedding_model_selection_v1.json")
    )
    assert selection.selection_version == EMBEDDING_MODEL_SELECTION_VERSION
    assert selection.primary_model.huggingface_model_id == "BAAI/bge-small-en-v1.5"
    assert selection.fallback_model.huggingface_model_id == "intfloat/e5-small-v2"
    assert selection.primary_model.embedding_dimension == 384
    assert selection.primary_similarity_metric is SemanticSimilarityMetric.COSINE
    assert selection.primary_model.normalize_embeddings is True


def test_storage_formula_matches_catalog_count() -> None:
    selection = load_productiq_embedding_model_selection(
        Path("resources/embedding/productiq_embedding_model_selection_v1.json")
    )
    dim = selection.primary_embedding_dimension
    raw_bytes = raw_float32_vector_storage_bytes(PRODUCTIQ_CATALOG_PRODUCT_COUNT, dim)
    assert raw_bytes == PRODUCTIQ_CATALOG_PRODUCT_COUNT * dim * 4
    mb = raw_bytes / 1_000_000
    assert mb == pytest.approx(selection.storage_raw_float32_bytes_per_product.dimension_384_mb, rel=0.01)


def test_query_instruction_present_on_primary() -> None:
    selection = load_productiq_embedding_model_selection(
        Path("resources/embedding/productiq_embedding_model_selection_v1.json")
    )
    assert "Represent this sentence" in selection.primary_model.query_encoding.instruction_prefix
    assert selection.primary_model.document_encoding.instruction_prefix == ""
