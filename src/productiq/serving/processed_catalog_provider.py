"""Processed Parquet catalog provider for product read API (Phase 13.5)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from productiq.exceptions.base import CatalogLoadError
from productiq.serving.catalog_read import (
    ProductCatalogReadProvider,
    catalog_read_model_from_processed_row,
)
from productiq.serving.product_schema import ProductCatalogReadModel

PROCESSED_CATALOG_READ_COLUMNS: tuple[str, ...] = (
    "product_id",
    "brand",
    "brand_normalized",
    "description",
    "image_url",
    "product_url",
    "category_gender",
    "product_type",
)

PARQUET_ENGINE = "pyarrow"


class ProcessedParquetProductCatalogReadProvider:
    """Load the processed catalog once and serve O(1) lookups by product_id."""

    def __init__(self, parquet_path: Path) -> None:
        self._parquet_path = Path(parquet_path)
        self._index: dict[str, ProductCatalogReadModel] = {}
        self._load_index()

    @property
    def parquet_path(self) -> Path:
        return self._parquet_path

    def get_product(self, product_id: str) -> ProductCatalogReadModel | None:
        return self._index.get(product_id)

    def _load_index(self) -> None:
        if not self._parquet_path.is_file():
            msg = "Processed product catalog artifact is not available"
            raise CatalogLoadError(msg)
        try:
            dataframe = pd.read_parquet(
                self._parquet_path,
                engine="pyarrow",
                columns=list(PROCESSED_CATALOG_READ_COLUMNS),
            )
        except Exception as exc:
            msg = "Failed to load processed product catalog"
            raise CatalogLoadError(msg) from exc
        if dataframe["product_id"].isna().any():
            msg = "Processed catalog contains null product_id values"
            raise CatalogLoadError(msg)
        index: dict[str, ProductCatalogReadModel] = {}
        for raw_row in dataframe.to_dict(orient="records"):
            row: dict[str, object] = {str(key): value for key, value in raw_row.items()}
            record = catalog_read_model_from_processed_row(row)
            index[record.product_id] = record
        self._index = index


def create_processed_parquet_catalog_provider(
    parquet_path: Path,
) -> ProductCatalogReadProvider:
    return ProcessedParquetProductCatalogReadProvider(parquet_path)


__all__ = [
    "PROCESSED_CATALOG_READ_COLUMNS",
    "ProcessedParquetProductCatalogReadProvider",
    "create_processed_parquet_catalog_provider",
]
