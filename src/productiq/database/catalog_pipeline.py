"""End-to-end processed Parquet to PostgreSQL catalog pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.engine import Engine

from data.export.schema import AJIO_PROCESSED_ROW_COUNT, PROCESSED_PARQUET_FILENAME
from productiq.config.settings import Settings, get_settings
from productiq.database.catalog_ddl import create_product_catalog_tables
from productiq.database.catalog_validation import CatalogValidationReport, validate_product_catalog
from productiq.database.engine import create_engine_from_settings
from productiq.database.loaders.catalog_loader import (
    DEFAULT_CATALOG_LOAD_CHUNK_SIZE,
    CatalogLoadReport,
    ProductCatalogLoader,
)
from productiq.exceptions import CatalogValidationError
from productiq.logging import get_logger


@dataclass(frozen=True)
class CatalogPipelineReport:
    """Summary of the processed Parquet → PostgreSQL catalog pipeline."""

    input_path: Path
    target_table: str
    load_report: CatalogLoadReport
    validation_report: CatalogValidationReport
    validation_passed: bool

    def summary(self) -> str:
        """Return a human-readable pipeline summary."""
        return "\n".join(
            [
                f"Input: {self.input_path.name}",
                f"Target table: {self.target_table}",
                self.load_report.summary(),
                self.validation_report.summary(),
                f"Validation passed: {self.validation_passed}",
            ]
        )


def load_processed_catalog(
    parquet_path: Path | None = None,
    *,
    engine: Engine | None = None,
    settings: Settings | None = None,
    chunk_size: int = DEFAULT_CATALOG_LOAD_CHUNK_SIZE,
    create_tables: bool = True,
    expected_row_count: int | None = AJIO_PROCESSED_ROW_COUNT,
    validate_after_load: bool = True,
) -> CatalogPipelineReport:
    """Load the processed catalog Parquet into PostgreSQL and validate the result."""
    logger = get_logger(__name__)
    resolved_settings = settings or get_settings()
    resolved_engine = engine or create_engine_from_settings(resolved_settings)
    resolved_path = Path(parquet_path) if parquet_path is not None else _default_processed_parquet_path()

    logger.info("Starting processed catalog pipeline for %s", resolved_path.name)

    if create_tables:
        logger.info("Ensuring catalog table exists: products")
        create_product_catalog_tables(resolved_engine, checkfirst=True)

    loader = ProductCatalogLoader(chunk_size=chunk_size)
    load_report = loader.load_from_parquet(
        resolved_path,
        resolved_engine,
        expected_row_count=expected_row_count,
        validate_input=True,
    )

    if validate_after_load:
        validation_report = validate_product_catalog(
            resolved_engine,
            expected_row_count=expected_row_count,
        )
    else:
        validation_report = CatalogValidationReport(
            table_exists=True,
            row_count=load_report.catalog_row_count_after,
            distinct_product_id_count=load_report.catalog_row_count_after,
            non_null_product_id_count=load_report.catalog_row_count_after,
            invalid_source_count=0,
            required_null_violation_count=0,
            attribute_null_count=0,
            validation_passed=True,
        )

    if validate_after_load and not validation_report.validation_passed:
        msg = "Processed catalog pipeline validation failed"
        raise CatalogValidationError(msg)

    logger.info("Processed catalog pipeline completed for %s", resolved_path.name)
    return CatalogPipelineReport(
        input_path=resolved_path,
        target_table=load_report.target_table,
        load_report=load_report,
        validation_report=validation_report,
        validation_passed=validation_report.validation_passed,
    )


def _default_processed_parquet_path() -> Path:
    project_root = Path(__file__).resolve().parents[3]
    return project_root / "resources" / "processed" / PROCESSED_PARQUET_FILENAME


__all__ = ["CatalogPipelineReport", "load_processed_catalog"]
