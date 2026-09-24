"""Processed Parquet input validation for catalog loading."""

from __future__ import annotations

from pathlib import Path

from data.export import ProcessedDatasetWriter
from productiq.exceptions import CatalogLoadError


def validate_processed_parquet(
    parquet_path: Path,
    *,
    expected_row_count: int | None = None,
) -> None:
    """Validate processed Parquet against the Phase 2.9 contract before loading."""
    resolved_path = Path(parquet_path)
    if not resolved_path.is_file():
        msg = f"Processed catalog Parquet not found: {resolved_path}"
        raise CatalogLoadError(msg)

    try:
        ProcessedDatasetWriter().validate(resolved_path, expected_row_count=expected_row_count)
    except Exception as exc:
        msg = f"Processed catalog Parquet validation failed for {resolved_path.name}"
        raise CatalogLoadError(msg) from exc


__all__ = ["validate_processed_parquet"]
