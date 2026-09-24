"""PostgreSQL integration tests for the product catalog foundation."""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from data.export import PROCESSED_COLUMN_ORDER, ProcessedDatasetWriter
from productiq.database.catalog_ddl import create_product_catalog_tables
from productiq.database.catalog_validation import validate_product_catalog
from productiq.database.loaders.catalog_loader import ProductCatalogLoader
from productiq.database.repository import ProductRepository
from tests.database.catalog_fixtures import make_product_record, make_product_records
from tests.database.test_integration import INTEGRATION_ENV_VAR, INTEGRATION_SKIP_REASON

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv(INTEGRATION_ENV_VAR) != "1", reason=INTEGRATION_SKIP_REASON),
]

FULL_CATALOG_ENV_VAR = "PRODUCTIQ_RUN_FULL_CATALOG_LOAD"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROCESSED_PARQUET_PATH = PROJECT_ROOT / "resources" / "processed" / "product_catalog.parquet"
AJIO_ROW_COUNT = 367_172


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


def _write_processed_parquet(path: Path, records: list[dict[str, object]]) -> None:
    dataframe = _records_to_processed_dataframe(records)
    ProcessedDatasetWriter().write(dataframe, path)


def test_catalog_table_creation(integration_engine: Engine, catalog_table: None) -> None:
    from sqlalchemy import inspect

    assert "products" in inspect(integration_engine).get_table_names()


def test_empty_catalog_count(integration_engine: Engine, catalog_table: None) -> None:
    session = sessionmaker(bind=integration_engine)()
    try:
        repository = ProductRepository(session)
        assert repository.count() == 0
    finally:
        session.close()


def test_loader_inserts_products(
    integration_engine: Engine,
    catalog_table: None,
    tmp_path: Path,
) -> None:
    parquet_path = tmp_path / "catalog.parquet"
    _write_processed_parquet(parquet_path, make_product_records(2))

    loader = ProductCatalogLoader(chunk_size=1)
    report = loader.load_from_parquet(parquet_path, integration_engine, expected_row_count=2)

    assert report.rows_read == 2
    assert report.catalog_row_count_after == 2
    assert report.rows_inserted == 2


def test_repository_get_and_filters(
    integration_engine: Engine,
    catalog_table: None,
    tmp_path: Path,
) -> None:
    parquet_path = tmp_path / "catalog.parquet"
    _write_processed_parquet(
        parquet_path,
        [
            make_product_record(product_id="1", brand_normalized="puma"),
            make_product_record(product_id="2", brand_normalized="nike", category_gender="Women"),
        ],
    )
    ProductCatalogLoader(chunk_size=10).load_from_parquet(parquet_path, integration_engine)

    session = sessionmaker(bind=integration_engine)()
    try:
        repository = ProductRepository(session)
        assert repository.get_by_id("1") is not None
        assert len(repository.find_by_brand("nike", limit=10, offset=0)) == 1
        assert len(repository.find_by_category("Women", limit=10, offset=0)) == 1
        assert len(repository.find_by_color("blue", limit=1, offset=0)) == 1
        assert repository.count() == 2
    finally:
        session.close()


def test_loader_is_idempotent(
    integration_engine: Engine,
    catalog_table: None,
    tmp_path: Path,
) -> None:
    parquet_path = tmp_path / "catalog.parquet"
    _write_processed_parquet(parquet_path, make_product_records(3))
    loader = ProductCatalogLoader(chunk_size=2)

    first = loader.load_from_parquet(parquet_path, integration_engine, expected_row_count=3)
    second = loader.load_from_parquet(parquet_path, integration_engine, expected_row_count=3)

    assert first.catalog_row_count_after == 3
    assert second.catalog_row_count_after == 3
    assert second.rows_inserted == 0
    assert second.rows_updated == second.rows_processed


def test_database_validation_after_load(
    integration_engine: Engine,
    catalog_table: None,
    tmp_path: Path,
) -> None:
    parquet_path = tmp_path / "catalog.parquet"
    _write_processed_parquet(parquet_path, make_product_records(4))
    ProductCatalogLoader(chunk_size=2).load_from_parquet(parquet_path, integration_engine)

    report = validate_product_catalog(integration_engine, expected_row_count=4)

    assert report.validation_passed
    assert report.row_count == report.distinct_product_id_count == 4


def test_source_constraint_rejects_invalid_source(
    integration_engine: Engine,
    catalog_table: None,
) -> None:
    with integration_engine.begin() as connection, pytest.raises(IntegrityError):
        connection.execute(
            text(
                "INSERT INTO products ("
                "product_id, product_url, brand, brand_normalized, description, image_url, "
                "category_gender, color_raw, color_normalized, color_is_coded, "
                "discount_price_inr, original_price_inr, price_anomaly, source"
                ") VALUES ("
                "'x', 'u', 'b', 'b', 'd', 'i', 'Men', 'c', 'c', false, 1, 2, false, 'other'"
                ")"
            )
        )


def test_pipeline_load_processed_catalog(
    integration_engine: Engine,
    catalog_table: None,
    tmp_path: Path,
) -> None:
    from productiq.database.catalog_pipeline import load_processed_catalog

    parquet_path = tmp_path / "catalog.parquet"
    _write_processed_parquet(parquet_path, make_product_records(2))

    report = load_processed_catalog(
        parquet_path,
        engine=integration_engine,
        create_tables=False,
        expected_row_count=2,
    )

    assert report.validation_passed
    assert report.load_report.catalog_row_count_after == 2


@pytest.mark.skipif(
    os.getenv(FULL_CATALOG_ENV_VAR) != "1" or not PROCESSED_PARQUET_PATH.is_file(),
    reason=f"Set {FULL_CATALOG_ENV_VAR}=1 and ensure processed Parquet exists",
)
def test_full_processed_catalog_load_and_idempotent_reload(integration_engine: Engine) -> None:
    create_product_catalog_tables(integration_engine, checkfirst=True)
    with integration_engine.begin() as connection:
        connection.execute(text("TRUNCATE TABLE products"))

    from productiq.database.catalog_pipeline import load_processed_catalog

    first = load_processed_catalog(
        PROCESSED_PARQUET_PATH,
        engine=integration_engine,
        create_tables=False,
        expected_row_count=AJIO_ROW_COUNT,
    )
    second = load_processed_catalog(
        PROCESSED_PARQUET_PATH,
        engine=integration_engine,
        create_tables=False,
        expected_row_count=AJIO_ROW_COUNT,
    )

    assert first.validation_report.row_count == AJIO_ROW_COUNT
    assert first.validation_report.distinct_product_id_count == AJIO_ROW_COUNT
    assert second.load_report.rows_inserted == 0
    assert second.validation_report.row_count == AJIO_ROW_COUNT
