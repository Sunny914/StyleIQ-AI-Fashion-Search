"""Data cleaning for ingested AJIO product datasets."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from data.ingestion.ajio import AJIO_COLUMNS
from productiq.exceptions import DataCleaningError
from productiq.logging import get_logger

AJIO_TEXT_COLUMNS = (
    "Product_URL",
    "Brand",
    "Description",
    "URL_image",
    "Category_by_gender",
    "Color",
)
AJIO_PRICE_COLUMNS = ("Discount Price (in Rs.)", "Original Price (in Rs.)")
PRICE_ANOMALY_COLUMN = "price_anomaly"


def _parse_price_string(value: object) -> int | None:
    """Parse a raw price string into an integer for cleaning."""
    if value is None:
        return None
    if isinstance(value, float) and pd.isna(value):
        return None
    if isinstance(value, int):
        return value
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    if stripped == "":
        return None
    return int(stripped.replace(",", ""))


@dataclass(frozen=True)
class CleaningReport:
    """Summary of transformations applied during cleaning."""

    input_row_count: int
    output_row_count: int
    columns_cleaned: tuple[str, ...]
    values_stripped: int
    prices_converted: int
    price_anomalies_flagged: int
    rows_removed: int

    def summary(self) -> str:
        """Return a human-readable cleaning summary."""
        return "\n".join(
            [
                f"Input rows: {self.input_row_count}",
                f"Output rows: {self.output_row_count}",
                f"Rows removed: {self.rows_removed}",
                f"Columns cleaned: {', '.join(self.columns_cleaned)}",
                f"Values stripped: {self.values_stripped}",
                f"Prices converted: {self.prices_converted}",
                f"Price anomalies flagged: {self.price_anomalies_flagged}",
            ]
        )


@dataclass(frozen=True)
class CleaningResult:
    """Cleaned dataset and associated cleaning report."""

    dataframe: pd.DataFrame
    report: CleaningReport


class AjioDataCleaner:
    """Clean AJIO raw DataFrames without semantic normalization."""

    def clean(self, dataframe: pd.DataFrame) -> CleaningResult:
        """Return a cleaned copy of ``dataframe`` and a structured report."""
        logger = get_logger(__name__)

        if not isinstance(dataframe, pd.DataFrame):
            msg = "Cleaning input must be a pandas DataFrame"
            raise DataCleaningError(msg)

        missing_columns = [column for column in AJIO_COLUMNS if column not in dataframe.columns]
        if missing_columns:
            msg = f"Missing required columns for cleaning: {', '.join(missing_columns)}"
            raise DataCleaningError(msg)

        input_row_count = len(dataframe)
        cleaned = dataframe.copy(deep=True)

        values_stripped = self._strip_surrounding_whitespace(cleaned)
        prices_converted = self._convert_price_columns(cleaned)
        price_anomalies_flagged = self._flag_price_anomalies(cleaned)

        columns_cleaned = (*AJIO_TEXT_COLUMNS, *AJIO_PRICE_COLUMNS, PRICE_ANOMALY_COLUMN)

        report = CleaningReport(
            input_row_count=input_row_count,
            output_row_count=len(cleaned),
            columns_cleaned=columns_cleaned,
            values_stripped=values_stripped,
            prices_converted=prices_converted,
            price_anomalies_flagged=price_anomalies_flagged,
            rows_removed=0,
        )

        logger.info(
            "Cleaned AJIO dataset: %s -> %s rows, %s price anomalies flagged",
            report.input_row_count,
            report.output_row_count,
            report.price_anomalies_flagged,
        )
        return CleaningResult(dataframe=cleaned, report=report)

    def _strip_surrounding_whitespace(self, dataframe: pd.DataFrame) -> int:
        stripped_count = 0

        for column in AJIO_TEXT_COLUMNS:
            original = dataframe[column]
            cleaned = original.map(lambda value: value.strip() if isinstance(value, str) else value)
            stripped_count += int((original != cleaned).sum())
            dataframe[column] = cleaned

        return stripped_count

    def _convert_price_columns(self, dataframe: pd.DataFrame) -> int:
        converted_count = 0

        for column in AJIO_PRICE_COLUMNS:
            original = dataframe[column]
            converted = original.map(_parse_price_string).astype("Int64")
            converted_count += int(original.notna().sum())
            dataframe[column] = converted

        return converted_count

    def _flag_price_anomalies(self, dataframe: pd.DataFrame) -> int:
        discount = dataframe["Discount Price (in Rs.)"]
        original = dataframe["Original Price (in Rs.)"]
        anomaly_mask = discount.notna() & original.notna() & (discount > original)
        anomaly_count = int(anomaly_mask.sum())
        dataframe[PRICE_ANOMALY_COLUMN] = anomaly_mask
        return anomaly_count
