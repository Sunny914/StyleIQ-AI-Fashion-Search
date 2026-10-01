"""Runtime artifact path configuration (Phase 14A)."""

from __future__ import annotations

from pathlib import Path

from productiq.config.database_config import reject_windows_absolute_path

DEFAULT_PROCESSED_CATALOG = Path("resources/processed/product_catalog.parquet")
DEFAULT_BM25_ARTIFACT = Path("resources/processed/bm25")
DEFAULT_EMBEDDINGS_ARTIFACT = Path("resources/processed/product_embeddings.parquet")
DEFAULT_MODEL_ARTIFACTS_DIR = Path("resources/models")


def normalize_artifact_path(value: str | Path, *, field_name: str) -> Path:
    """Normalize artifact paths; reject Windows drive-letter absolutes."""
    text = str(value).strip()
    if not text:
        msg = f"{field_name} must be non-empty"
        raise ValueError(msg)
    reject_windows_absolute_path(text, field_name=field_name)
    path = Path(text)
    if path.is_absolute() and path.drive:
        msg = f"{field_name} must not be a Windows absolute path"
        raise ValueError(msg)
    return path


__all__ = [
    "DEFAULT_BM25_ARTIFACT",
    "DEFAULT_EMBEDDINGS_ARTIFACT",
    "DEFAULT_MODEL_ARTIFACTS_DIR",
    "DEFAULT_PROCESSED_CATALOG",
    "normalize_artifact_path",
]
