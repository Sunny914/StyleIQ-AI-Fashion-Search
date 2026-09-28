"""Unit tests for embedding artifact validation before vector index build."""

from __future__ import annotations

from pathlib import Path

import pytest

from productiq.exceptions.base import SemanticRetrievalError
from productiq.retrieval.embedding_schema import (
    PRODUCT_EMBEDDINGS_FILENAME,
    PRODUCT_EMBEDDINGS_MANIFEST_FILENAME,
)
from productiq.retrieval.vector_index_loader import validate_embedding_artifact_for_vector_index

PROJECT_ROOT = Path(__file__).resolve().parents[2]
EMBEDDINGS_PATH = PROJECT_ROOT / "resources" / "processed" / PRODUCT_EMBEDDINGS_FILENAME
MANIFEST_PATH = PROJECT_ROOT / "resources" / "processed" / PRODUCT_EMBEDDINGS_MANIFEST_FILENAME


@pytest.mark.skipif(not EMBEDDINGS_PATH.is_file(), reason="official embedding artifact unavailable")
def test_validate_official_embedding_artifact_for_vector_index() -> None:
    manifest = validate_embedding_artifact_for_vector_index(
        EMBEDDINGS_PATH,
        manifest_path=MANIFEST_PATH,
        enforce_official_checksums=True,
    )
    assert manifest.product_count == 367_172
    assert manifest.embedding_dimension == 384


def test_validate_embedding_artifact_rejects_missing_file(tmp_path: Path) -> None:
    missing = tmp_path / "missing.parquet"
    with pytest.raises(SemanticRetrievalError):
        validate_embedding_artifact_for_vector_index(
            missing,
            enforce_official_checksums=False,
        )
