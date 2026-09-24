"""Unit tests for product catalog loader helpers."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from data.export import PROCESSED_COLUMN_ORDER, ProcessedDatasetWriter
from productiq.database.loaders.catalog_loader import (
    DEFAULT_CATALOG_LOAD_CHUNK_SIZE,
    ProductCatalogLoader,
    _dataframe_chunk_to_records,
)
from productiq.exceptions import CatalogLoadError
from tests.database.catalog_fixtures import make_product_record, make_product_records


def test_default_chunk_size_is_documented() -> None:
    assert DEFAULT_CATALOG_LOAD_CHUNK_SIZE == 10_000


def test_dataframe_chunk_to_records_preserves_nullable_attributes() -> None:
    dataframe = pd.DataFrame([make_product_record(sleeve=None)])
    for column in ("discount_price_inr", "original_price_inr"):
        dataframe[column] = dataframe[column].astype("Int64")
    for column in ("color_is_coded", "price_anomaly"):
        dataframe[column] = dataframe[column].astype("boolean")
    for column in PROCESSED_COLUMN_ORDER:
        if column not in ("discount_price_inr", "original_price_inr", "color_is_coded", "price_anomaly"):
            dataframe[column] = dataframe[column].astype("string")

    records = _dataframe_chunk_to_records(dataframe)

    assert records[0]["sleeve"] is None
    assert records[0]["product_id"] == "123456789001"


def test_loader_rejects_non_positive_chunk_size() -> None:
    with pytest.raises(CatalogLoadError, match="chunk_size must be positive"):
        ProductCatalogLoader(chunk_size=0)


def test_validate_processed_parquet_accepts_written_fixture(tmp_path: Path) -> None:
    from productiq.database.loaders.parquet_input import validate_processed_parquet

    dataframe = _records_to_processed_dataframe(make_product_records(2))
    parquet_path = tmp_path / "catalog.parquet"
    ProcessedDatasetWriter().write(dataframe, parquet_path)

    validate_processed_parquet(parquet_path)


def _records_to_processed_dataframe(records: list[dict[str, object]]) -> pd.DataFrame:
    dataframe = pd.DataFrame(records)
    for column in ("discount_price_inr", "original_price_inr"):
        dataframe[column] = dataframe[column].astype("Int64")
    for column in ("color_is_coded", "price_anomaly"):
        dataframe[column] = dataframe[column].astype("boolean")
    for column in PROCESSED_COLUMN_ORDER:
        if column not in ("discount_price_inr", "original_price_inr", "color_is_coded", "price_anomaly"):
            dataframe[column] = dataframe[column].astype("string")
    return dataframe.loc[:, list(PROCESSED_COLUMN_ORDER)]
