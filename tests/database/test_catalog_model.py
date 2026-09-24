"""Unit tests for the Product catalog ORM schema."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from data.export.schema import PROCESSED_COLUMN_ORDER
from productiq.database.catalog_contract import (
    CATALOG_NULLABLE_ATTRIBUTE_COLUMNS,
    CATALOG_REQUIRED_COLUMNS,
    CATALOG_SOURCE_CHECK_VALUE,
    PRODUCT_CATALOG_DB_SCHEMA_VERSION,
    PRODUCTS_TABLE_NAME,
)
from productiq.database.models.product import Product


def test_product_table_name() -> None:
    assert Product.__tablename__ == PRODUCTS_TABLE_NAME == "products"


def test_product_catalog_db_schema_version_matches_processed_contract() -> None:
    assert PRODUCT_CATALOG_DB_SCHEMA_VERSION == "1.0.0"


def test_product_model_column_names_match_processed_contract() -> None:
    column_names = {column.name for column in Product.__table__.columns}
    assert column_names == set(PROCESSED_COLUMN_ORDER)
    assert tuple(Product.__table__.columns.keys()) == tuple(PROCESSED_COLUMN_ORDER)


def test_product_primary_key_is_product_id() -> None:
    primary_key = Product.__table__.primary_key
    assert [column.name for column in primary_key.columns] == ["product_id"]


def test_required_columns_are_not_nullable() -> None:
    table = Product.__table__
    for column_name in CATALOG_REQUIRED_COLUMNS:
        assert table.c[column_name].nullable is False, column_name


def test_attribute_columns_are_nullable() -> None:
    table = Product.__table__
    for column_name in CATALOG_NULLABLE_ATTRIBUTE_COLUMNS:
        assert table.c[column_name].nullable is True, column_name


def test_product_column_sqlalchemy_types() -> None:
    table = Product.__table__
    non_text_columns = {
        "color_is_coded",
        "price_anomaly",
        "discount_price_inr",
        "original_price_inr",
    }

    for column_name in PROCESSED_COLUMN_ORDER:
        if column_name in non_text_columns:
            continue
        assert isinstance(table.c[column_name].type, sa.Text), column_name

    assert isinstance(table.c.color_is_coded.type, sa.Boolean)
    assert isinstance(table.c.price_anomaly.type, sa.Boolean)
    assert isinstance(table.c.discount_price_inr.type, sa.Integer)
    assert isinstance(table.c.original_price_inr.type, sa.Integer)


def test_source_check_constraint_exists() -> None:
    check_names = {
        constraint.name
        for constraint in Product.__table__.constraints
        if isinstance(constraint, sa.CheckConstraint)
    }
    assert "ck_products_source_ajio" in check_names


def test_expected_catalog_indexes_exist() -> None:
    index_names = {index.name for index in Product.__table__.indexes}
    assert index_names == {
        "ix_products_brand_normalized",
        "ix_products_category_gender",
        "ix_products_color_normalized",
        "ix_products_source",
    }


def test_postgresql_ddl_includes_products_table_and_source_check() -> None:
    from sqlalchemy.schema import CreateTable

    ddl = str(CreateTable(Product.__table__).compile(dialect=postgresql.dialect()))
    assert "products" in ddl
    assert CATALOG_SOURCE_CHECK_VALUE in ddl


def test_create_product_catalog_tables_uses_metadata_create_all(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from productiq.database.base import Base
    from productiq.database.catalog_ddl import create_product_catalog_tables

    engine = MagicMock()
    calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def spy_create_all(*args: object, **kwargs: object) -> None:
        calls.append((args, kwargs))

    monkeypatch.setattr(Base.metadata, "create_all", spy_create_all)
    create_product_catalog_tables(engine, checkfirst=True)

    assert len(calls) == 1
    assert calls[0][0][0] is engine
    assert calls[0][1]["checkfirst"] is True
