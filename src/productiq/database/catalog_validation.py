"""PostgreSQL product catalog validation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import Boolean, Integer, Text, func, inspect, select, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.engine.reflection import Inspector

from productiq.database.catalog_contract import (
    CATALOG_COLUMN_ORDER,
    CATALOG_NULLABLE_ATTRIBUTE_COLUMNS,
    CATALOG_REQUIRED_COLUMNS,
    CATALOG_SOURCE_CHECK_VALUE,
    PRODUCTS_TABLE_NAME,
)
from productiq.database.models.product import Product
from productiq.exceptions import CatalogValidationError

EXPECTED_INDEX_NAMES = frozenset(
    {
        "ix_products_brand_normalized",
        "ix_products_category_gender",
        "ix_products_color_normalized",
        "ix_products_source",
    }
)
EXPECTED_CHECK_CONSTRAINT_NAMES = frozenset({"ck_products_source_ajio"})


@dataclass(frozen=True)
class CatalogValidationReport:
    """Summary of PostgreSQL catalog validation."""

    table_exists: bool
    row_count: int
    distinct_product_id_count: int
    non_null_product_id_count: int
    invalid_source_count: int
    required_null_violation_count: int
    attribute_null_count: int
    validation_passed: bool

    def summary(self) -> str:
        """Return a human-readable validation summary."""
        return "\n".join(
            [
                f"Table exists: {self.table_exists}",
                f"Row count: {self.row_count}",
                f"Distinct product_id: {self.distinct_product_id_count}",
                f"Non-null product_id rows: {self.non_null_product_id_count}",
                f"Invalid source rows: {self.invalid_source_count}",
                f"Required-column null violations: {self.required_null_violation_count}",
                f"Attribute null cells: {self.attribute_null_count}",
                f"Validation passed: {self.validation_passed}",
            ]
        )


def validate_product_catalog(
    engine: Engine,
    *,
    expected_row_count: int | None = None,
) -> CatalogValidationReport:
    """Validate the PostgreSQL products table against the catalog contract."""
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    if PRODUCTS_TABLE_NAME not in table_names:
        msg = f"Catalog table not found: {PRODUCTS_TABLE_NAME}"
        raise CatalogValidationError(msg)

    _validate_table_columns(inspector)
    _validate_table_indexes(inspector)
    _validate_table_checks(inspector)

    with engine.connect() as connection:
        row_count = int(
            connection.execute(select(func.count()).select_from(Product.__table__)).scalar_one()
        )
        distinct_product_id_count = int(
            connection.execute(
                select(func.count(func.distinct(Product.product_id))).select_from(Product.__table__)
            ).scalar_one()
        )
        non_null_product_id_count = int(
            connection.execute(
                select(func.count())
                .select_from(Product.__table__)
                .where(Product.product_id.is_not(None))
            ).scalar_one()
        )
        invalid_source_count = int(
            connection.execute(
                text(
                    f"SELECT COUNT(*) FROM {PRODUCTS_TABLE_NAME} "
                    "WHERE source <> :source_value"
                ),
                {"source_value": CATALOG_SOURCE_CHECK_VALUE},
            ).scalar_one()
        )
        required_null_violation_count = _count_required_null_violations(connection)
        attribute_null_count = _count_attribute_null_cells(connection)

    validation_passed = (
        row_count == distinct_product_id_count == non_null_product_id_count
        and invalid_source_count == 0
        and required_null_violation_count == 0
    )
    if expected_row_count is not None:
        validation_passed = validation_passed and row_count == expected_row_count

    if not validation_passed:
        msg = f"Catalog validation failed for table {PRODUCTS_TABLE_NAME}"
        raise CatalogValidationError(msg)

    return CatalogValidationReport(
        table_exists=True,
        row_count=row_count,
        distinct_product_id_count=distinct_product_id_count,
        non_null_product_id_count=non_null_product_id_count,
        invalid_source_count=invalid_source_count,
        required_null_violation_count=required_null_violation_count,
        attribute_null_count=attribute_null_count,
        validation_passed=True,
    )


def _validate_table_columns(inspector: Inspector) -> None:
    column_info = {column["name"]: column for column in inspector.get_columns(PRODUCTS_TABLE_NAME)}
    if set(column_info) != set(CATALOG_COLUMN_ORDER):
        msg = "Catalog table columns do not match the ProductIQ contract"
        raise CatalogValidationError(msg)

    for column_name in CATALOG_REQUIRED_COLUMNS:
        if column_info[column_name]["nullable"] is not False:
            msg = f"Required catalog column must be NOT NULL: {column_name}"
            raise CatalogValidationError(msg)

    for column_name in CATALOG_NULLABLE_ATTRIBUTE_COLUMNS:
        if column_info[column_name]["nullable"] is not True:
            msg = f"Attribute catalog column must be nullable: {column_name}"
            raise CatalogValidationError(msg)

    _validate_column_types({name: dict(column) for name, column in column_info.items()})


def _validate_column_types(column_info: dict[str, dict[str, Any]]) -> None:
    text_columns = set(CATALOG_COLUMN_ORDER) - {
        "color_is_coded",
        "price_anomaly",
        "discount_price_inr",
        "original_price_inr",
    }
    for column_name in text_columns:
        if not isinstance(column_info[column_name]["type"], Text):
            msg = f"Catalog column must use TEXT type: {column_name}"
            raise CatalogValidationError(msg)

    for column_name in ("color_is_coded", "price_anomaly"):
        if not isinstance(column_info[column_name]["type"], Boolean):
            msg = f"Catalog column must use BOOLEAN type: {column_name}"
            raise CatalogValidationError(msg)

    for column_name in ("discount_price_inr", "original_price_inr"):
        if not isinstance(column_info[column_name]["type"], Integer):
            msg = f"Catalog column must use INTEGER type: {column_name}"
            raise CatalogValidationError(msg)


def _validate_table_indexes(inspector: Inspector) -> None:
    index_names = {index["name"] for index in inspector.get_indexes(PRODUCTS_TABLE_NAME)}
    missing = EXPECTED_INDEX_NAMES - index_names
    if missing:
        msg = f"Missing expected catalog indexes: {', '.join(sorted(missing))}"
        raise CatalogValidationError(msg)


def _validate_table_checks(inspector: Inspector) -> None:
    checks = inspector.get_check_constraints(PRODUCTS_TABLE_NAME)
    check_names = {check["name"] for check in checks if check.get("name")}
    missing = EXPECTED_CHECK_CONSTRAINT_NAMES - check_names
    if missing:
        msg = f"Missing expected catalog check constraints: {', '.join(sorted(missing))}"
        raise CatalogValidationError(msg)


def _count_required_null_violations(connection: Connection) -> int:
    conditions = " OR ".join(f"{column} IS NULL" for column in CATALOG_REQUIRED_COLUMNS)
    query = text(f"SELECT COUNT(*) FROM {PRODUCTS_TABLE_NAME} WHERE {conditions}")
    return int(connection.execute(query).scalar_one())


def _count_attribute_null_cells(connection: Connection) -> int:
    expressions = " + ".join(
        f"CASE WHEN {column} IS NULL THEN 1 ELSE 0 END"
        for column in CATALOG_NULLABLE_ATTRIBUTE_COLUMNS
    )
    query = text(f"SELECT COALESCE(SUM({expressions}), 0) FROM {PRODUCTS_TABLE_NAME}")
    return int(connection.execute(query).scalar_one())


__all__ = ["CatalogValidationReport", "validate_product_catalog"]
