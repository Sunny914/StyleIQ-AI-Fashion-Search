"""Build ProductIQ canonical product dataframes from prepared AJIO data."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from data.catalog.schema import (
    AJIO_SOURCE_NAME,
    CANONICAL_COLUMN_COUNT,
    CANONICAL_COLUMN_ORDER,
    CANONICAL_FIELD_DEFINITIONS,
    REQUIRED_SOURCE_COLUMNS,
)
from productiq.exceptions import DataCatalogError
from productiq.logging import get_logger


@dataclass(frozen=True)
class CanonicalBuildReport:
    """Summary of a canonical dataframe build."""

    input_row_count: int
    output_row_count: int
    canonical_column_count: int
    source_value: str
    null_product_id_count: int
    duplicate_product_id_count: int
    row_count_preserved: bool

    def summary(self) -> str:
        """Return a human-readable build summary."""
        return "\n".join(
            [
                f"Input rows: {self.input_row_count}",
                f"Output rows: {self.output_row_count}",
                f"Canonical columns: {self.canonical_column_count}",
                f"Source value: {self.source_value}",
                f"Null product_id rows: {self.null_product_id_count}",
                f"Duplicate product_id rows: {self.duplicate_product_id_count}",
                f"Row count preserved: {self.row_count_preserved}",
            ]
        )


@dataclass(frozen=True)
class CanonicalBuildResult:
    """Canonical product dataframe and associated build report."""

    dataframe: pd.DataFrame
    report: CanonicalBuildReport


class AjioCanonicalProductBuilder:
    """Map deduplicated prepared AJIO rows to the ProductIQ canonical schema."""

    def build(self, dataframe: pd.DataFrame) -> CanonicalBuildResult:
        """Build a canonical ProductIQ dataframe without mutating the input."""
        logger = get_logger(__name__)

        if not isinstance(dataframe, pd.DataFrame):
            msg = "Canonical build input must be a pandas DataFrame"
            raise DataCatalogError(msg)

        missing_columns = [
            column for column in REQUIRED_SOURCE_COLUMNS if column not in dataframe.columns
        ]
        if missing_columns:
            msg = f"Missing required source columns for canonical build: {', '.join(missing_columns)}"
            raise DataCatalogError(msg)

        input_row_count = len(dataframe)
        canonical_columns: dict[str, pd.Series] = {}

        for field in CANONICAL_FIELD_DEFINITIONS:
            if field.canonical_name == "source":
                canonical_columns[field.canonical_name] = pd.Series(
                    [AJIO_SOURCE_NAME] * input_row_count,
                    index=dataframe.index,
                    dtype=field.dtype,
                )
                continue

            source_column = field.source_column
            if source_column is None:
                msg = f"Canonical field {field.canonical_name} is missing a source mapping"
                raise DataCatalogError(msg)

            series = dataframe[source_column]
            if field.dtype == "string":
                canonical_columns[field.canonical_name] = series.astype("string")
            elif field.dtype == "Int64":
                canonical_columns[field.canonical_name] = series.astype("Int64")
            elif field.dtype == "boolean":
                canonical_columns[field.canonical_name] = series.astype("boolean")
            else:
                msg = f"Unsupported canonical dtype for {field.canonical_name}: {field.dtype}"
                raise DataCatalogError(msg)

        canonical = pd.DataFrame(canonical_columns, columns=list(CANONICAL_COLUMN_ORDER))

        product_ids = canonical["product_id"]
        null_product_id_count = int(product_ids.isna().sum())
        non_null_ids = product_ids.dropna().astype("string")
        null_product_id_count += int((non_null_ids.str.strip() == "").sum())
        if null_product_id_count:
            msg = f"Canonical build found {null_product_id_count} null or empty product_id values"
            raise DataCatalogError(msg)

        duplicate_product_id_count = int(canonical["product_id"].duplicated(keep=False).sum())
        if duplicate_product_id_count:
            msg = (
                "Canonical build found duplicate product_id values "
                f"({duplicate_product_id_count} rows)"
            )
            raise DataCatalogError(msg)

        if not (canonical["source"] == AJIO_SOURCE_NAME).all():
            msg = "Canonical source column must contain only the expected AJIO source value"
            raise DataCatalogError(msg)

        output_row_count = len(canonical)
        if output_row_count != input_row_count:
            msg = (
                f"Canonical build row count mismatch: input={input_row_count}, "
                f"output={output_row_count}"
            )
            raise DataCatalogError(msg)

        if list(canonical.columns) != list(CANONICAL_COLUMN_ORDER):
            msg = "Canonical dataframe column order does not match the schema definition"
            raise DataCatalogError(msg)

        if len(canonical.columns) != CANONICAL_COLUMN_COUNT:
            msg = (
                f"Canonical dataframe must contain {CANONICAL_COLUMN_COUNT} columns, "
                f"found {len(canonical.columns)}"
            )
            raise DataCatalogError(msg)

        report = CanonicalBuildReport(
            input_row_count=input_row_count,
            output_row_count=output_row_count,
            canonical_column_count=len(canonical.columns),
            source_value=AJIO_SOURCE_NAME,
            null_product_id_count=null_product_id_count,
            duplicate_product_id_count=duplicate_product_id_count,
            row_count_preserved=output_row_count == input_row_count,
        )

        logger.info(
            "Built AJIO canonical product dataframe with %s rows and %s columns",
            report.output_row_count,
            report.canonical_column_count,
        )
        return CanonicalBuildResult(dataframe=canonical, report=report)
