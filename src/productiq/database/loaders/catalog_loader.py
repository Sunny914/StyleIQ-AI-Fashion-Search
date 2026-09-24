"""Chunked PostgreSQL loader for the processed product catalog."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import pandas as pd
import pyarrow.parquet as pq  # type: ignore[import-untyped]
from sqlalchemy import Table
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from data.export.schema import PROCESSED_COLUMN_ORDER
from productiq.database.catalog_contract import PRODUCTS_TABLE_NAME
from productiq.database.loaders.parquet_input import validate_processed_parquet
from productiq.database.models.product import Product
from productiq.database.repository import ProductRepository
from productiq.exceptions import CatalogLoadError
from productiq.logging import get_logger

# Default batch size balances memory use and PostgreSQL write throughput.
DEFAULT_CATALOG_LOAD_CHUNK_SIZE = 10_000
POSTGRESQL_MAX_PARAMETERS = 65_535
MAX_UPSERT_ROWS_PER_STATEMENT = POSTGRESQL_MAX_PARAMETERS // len(PROCESSED_COLUMN_ORDER)


@dataclass(frozen=True)
class CatalogLoadReport:
    """Summary of a processed catalog load operation."""

    input_path: Path
    target_table: str
    rows_read: int
    rows_processed: int
    rows_upserted: int
    rows_inserted: int
    rows_updated: int
    catalog_row_count_before: int
    catalog_row_count_after: int
    chunk_size: int

    def summary(self) -> str:
        """Return a human-readable load summary."""
        return "\n".join(
            [
                f"Input: {self.input_path.name}",
                f"Target table: {self.target_table}",
                f"Rows read: {self.rows_read}",
                f"Rows processed: {self.rows_processed}",
                f"Rows upserted: {self.rows_upserted}",
                f"Rows inserted: {self.rows_inserted}",
                f"Rows updated: {self.rows_updated}",
                f"Catalog rows before: {self.catalog_row_count_before}",
                f"Catalog rows after: {self.catalog_row_count_after}",
                f"Chunk size: {self.chunk_size}",
            ]
        )


class ProductCatalogLoader:
    """Load processed Parquet catalog rows into PostgreSQL using chunked upserts."""

    def __init__(
        self,
        *,
        chunk_size: int = DEFAULT_CATALOG_LOAD_CHUNK_SIZE,
        session_factory: sessionmaker[Session] | None = None,
    ) -> None:
        if chunk_size <= 0:
            msg = "Catalog loader chunk_size must be positive"
            raise CatalogLoadError(msg)
        self.chunk_size = chunk_size
        self._session_factory = session_factory

    def load_from_parquet(
        self,
        parquet_path: Path,
        engine: Engine,
        *,
        expected_row_count: int | None = None,
        validate_input: bool = True,
    ) -> CatalogLoadReport:
        """Load a processed Parquet file into the products table."""
        logger = get_logger(__name__)
        resolved_path = Path(parquet_path)

        if validate_input:
            logger.info("Validating processed catalog input: %s", resolved_path.name)
            validate_processed_parquet(resolved_path, expected_row_count=expected_row_count)

        parquet_file = pq.ParquetFile(resolved_path)
        rows_read = parquet_file.metadata.num_rows
        if expected_row_count is not None and rows_read != expected_row_count:
            msg = (
                f"Processed catalog row count mismatch for {resolved_path.name}: "
                f"expected={expected_row_count}, found={rows_read}"
            )
            raise CatalogLoadError(msg)

        session_factory = self._session_factory or sessionmaker(
            bind=engine,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )

        rows_processed = 0
        rows_upserted = 0
        catalog_row_count_before = 0
        catalog_row_count_after = 0

        logger.info(
            "Starting catalog load (%s rows, chunk_size=%s)",
            rows_read,
            self.chunk_size,
        )

        session = session_factory()
        try:
            repository = ProductRepository(session)
            catalog_row_count_before = repository.count()

            for batch_index, batch in enumerate(
                parquet_file.iter_batches(batch_size=self.chunk_size),
                start=1,
            ):
                chunk = batch.to_pandas()
                chunk = chunk.loc[:, list(PROCESSED_COLUMN_ORDER)]
                records = _dataframe_chunk_to_records(chunk)
                for start in range(0, len(records), MAX_UPSERT_ROWS_PER_STATEMENT):
                    batch_records = records[start : start + MAX_UPSERT_ROWS_PER_STATEMENT]
                    rows_upserted += _upsert_records(session, batch_records)
                rows_processed += len(records)
                session.commit()
                logger.info(
                    "Catalog load batch %s complete (%s/%s rows processed)",
                    batch_index,
                    rows_processed,
                    rows_read,
                )

            catalog_row_count_after = repository.count()
        except Exception as exc:
            session.rollback()
            msg = f"Catalog load failed for table {PRODUCTS_TABLE_NAME}"
            raise CatalogLoadError(msg) from exc
        finally:
            session.close()

        rows_inserted = max(0, catalog_row_count_after - catalog_row_count_before)
        if rows_inserted == 0 and rows_processed > 0:
            rows_updated = rows_processed
        else:
            rows_updated = max(0, rows_upserted - rows_inserted)

        report = CatalogLoadReport(
            input_path=resolved_path,
            target_table=PRODUCTS_TABLE_NAME,
            rows_read=rows_read,
            rows_processed=rows_processed,
            rows_upserted=rows_upserted,
            rows_inserted=rows_inserted,
            rows_updated=rows_updated,
            catalog_row_count_before=catalog_row_count_before,
            catalog_row_count_after=catalog_row_count_after,
            chunk_size=self.chunk_size,
        )
        logger.info("Catalog load completed for %s", resolved_path.name)
        return report


def _dataframe_chunk_to_records(dataframe: pd.DataFrame) -> list[dict[str, Any]]:
    ordered = dataframe.loc[:, list(PROCESSED_COLUMN_ORDER)]
    records: list[dict[str, Any]] = []
    for row in ordered.to_dict(orient="records"):
        cleaned_row: dict[str, Any] = {}
        for key, value in row.items():
            key_str = str(key)
            cleaned_row[key_str] = None if value is pd.NA or pd.isna(value) else value
        records.append(cleaned_row)
    return records


def _upsert_records(session: Session, records: list[dict[str, Any]]) -> int:
    if not records:
        return 0

    table = cast(Table, Product.__table__)
    insert_stmt = insert(table).values(records)
    update_columns = {
        column.name: insert_stmt.excluded[column.name]
        for column in table.columns
        if column.name != "product_id"
    }
    upsert_stmt = insert_stmt.on_conflict_do_update(
        index_elements=[table.c.product_id],
        set_=update_columns,
    )
    result = session.execute(upsert_stmt)
    rowcount = getattr(result, "rowcount", 0)
    return int(rowcount or 0)


__all__ = [
    "DEFAULT_CATALOG_LOAD_CHUNK_SIZE",
    "CatalogLoadReport",
    "ProductCatalogLoader",
]
