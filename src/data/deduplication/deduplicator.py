"""Conservative deduplication for prepared AJIO datasets."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from data.deduplication.profiling import ID_PRODUCT_COLUMN
from data.ingestion.ajio import AJIO_COLUMNS
from data.preprocessing.cleaning import PRICE_ANOMALY_COLUMN
from data.preprocessing.normalization import (
    BRAND_NORMALIZED_COLUMN,
    COLOR_IS_CODED_COLUMN,
    COLOR_NORMALIZED_COLUMN,
)
from productiq.exceptions import DataDeduplicationError
from productiq.logging import get_logger

PREPARED_REQUIRED_COLUMNS = (
    *AJIO_COLUMNS,
    "Discount Price (in Rs.)",
    "Original Price (in Rs.)",
    PRICE_ANOMALY_COLUMN,
    BRAND_NORMALIZED_COLUMN,
    COLOR_NORMALIZED_COLUMN,
    COLOR_IS_CODED_COLUMN,
)

DEDUPLICATION_POLICY_SUMMARY = (
    "ProductIQ currently treats Id_Product as the stable catalog-record identifier. "
    "Business-attribute similarity is not sufficient evidence to merge records because "
    "the source dataset does not expose an explicit parent-product or variant relationship. "
    "Only exact duplicate rows are removed. Product_URL, URL_image, and business-attribute "
    "duplicate patterns are preserved."
)


@dataclass(frozen=True)
class DeduplicationReport:
    """Summary of a conservative deduplication run."""

    input_row_count: int
    output_row_count: int
    exact_duplicate_rows_detected: int
    exact_duplicate_rows_removed: int
    duplicate_id_product_rows: int
    rows_preserved_as_potential_variants: int
    rows_removed: int
    policy_summary: str

    def summary(self) -> str:
        """Return a human-readable deduplication summary."""
        return "\n".join(
            [
                f"Input rows: {self.input_row_count}",
                f"Output rows: {self.output_row_count}",
                f"Rows removed: {self.rows_removed}",
                f"Exact duplicate rows detected: {self.exact_duplicate_rows_detected}",
                f"Exact duplicate rows removed: {self.exact_duplicate_rows_removed}",
                f"Duplicate Id_Product rows: {self.duplicate_id_product_rows}",
                (
                    "Rows preserved as potential variants: "
                    f"{self.rows_preserved_as_potential_variants}"
                ),
                f"Policy: {self.policy_summary}",
            ]
        )


@dataclass(frozen=True)
class DeduplicationResult:
    """Deduplicated dataset and associated report."""

    dataframe: pd.DataFrame
    report: DeduplicationReport


class AjioDataDeduplicator:
    """Apply conservative deduplication without merging catalog variants."""

    def deduplicate(self, dataframe: pd.DataFrame) -> DeduplicationResult:
        """Remove exact duplicate rows and preserve all other records."""
        logger = get_logger(__name__)

        if not isinstance(dataframe, pd.DataFrame):
            msg = "Deduplication input must be a pandas DataFrame"
            raise DataDeduplicationError(msg)

        missing_columns = [
            column for column in PREPARED_REQUIRED_COLUMNS if column not in dataframe.columns
        ]
        if missing_columns:
            msg = f"Missing required columns for deduplication: {', '.join(missing_columns)}"
            raise DataDeduplicationError(msg)

        input_row_count = len(dataframe)
        duplicate_id_product_rows = self._count_id_product_conflicts(dataframe)
        if duplicate_id_product_rows:
            msg = (
                "Duplicate Id_Product values detected "
                f"({duplicate_id_product_rows} rows). "
                "Deduplication refuses to silently remove catalog identity conflicts."
            )
            raise DataDeduplicationError(msg)

        exact_duplicate_rows_removed = int(dataframe.duplicated(keep="first").sum())
        exact_duplicate_rows_detected = int(dataframe.duplicated(keep=False).sum())
        deduplicated = dataframe[~dataframe.duplicated(keep="first")].copy(deep=True)
        output_row_count = len(deduplicated)
        rows_removed = input_row_count - output_row_count

        report = DeduplicationReport(
            input_row_count=input_row_count,
            output_row_count=output_row_count,
            exact_duplicate_rows_detected=exact_duplicate_rows_detected,
            exact_duplicate_rows_removed=exact_duplicate_rows_removed,
            duplicate_id_product_rows=duplicate_id_product_rows,
            rows_preserved_as_potential_variants=output_row_count,
            rows_removed=rows_removed,
            policy_summary=DEDUPLICATION_POLICY_SUMMARY,
        )

        logger.info(
            "Deduplicated AJIO dataset: %s -> %s rows (%s exact duplicate rows removed)",
            report.input_row_count,
            report.output_row_count,
            report.exact_duplicate_rows_removed,
        )
        return DeduplicationResult(dataframe=deduplicated, report=report)

    def _count_id_product_conflicts(self, dataframe: pd.DataFrame) -> int:
        """Count rows participating in non-exact Id_Product conflicts."""
        conflict_rows = 0
        for _, group in dataframe.groupby(ID_PRODUCT_COLUMN, dropna=False):
            if len(group) < 2:
                continue
            if len(group.drop_duplicates()) > 1:
                conflict_rows += len(group)
        return conflict_rows
