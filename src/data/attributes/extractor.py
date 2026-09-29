"""Deterministic product attribute extraction from canonical data."""

from __future__ import annotations

from dataclasses import dataclass
from functools import partial

import pandas as pd

from data.attributes.rules import extract_attribute_value, normalize_attribute_text
from data.attributes.schema import (
    ATTRIBUTE_COLUMN_ORDER,
    ATTRIBUTE_DEFINITIONS,
    ATTRIBUTE_TEXT_COLUMN,
    REQUIRED_CANONICAL_COLUMNS,
)
from productiq.exceptions import DataAttributeError
from productiq.logging import get_logger


@dataclass(frozen=True)
class AttributeExtractionReport:
    """Summary of deterministic attribute extraction."""

    input_row_count: int
    output_row_count: int
    attributes_added: tuple[str, ...]
    matched_row_counts: dict[str, int]
    unmatched_row_counts: dict[str, int]
    row_count_preserved: bool
    row_order_preserved: bool

    def summary(self) -> str:
        """Return a human-readable extraction summary."""
        lines = [
            f"Input rows: {self.input_row_count}",
            f"Output rows: {self.output_row_count}",
            f"Attributes added: {', '.join(self.attributes_added)}",
            f"Row count preserved: {self.row_count_preserved}",
            f"Row order preserved: {self.row_order_preserved}",
        ]
        for attribute in self.attributes_added:
            lines.append(
                f"{attribute}: matched={self.matched_row_counts[attribute]}, "
                f"unmatched={self.unmatched_row_counts[attribute]}"
            )
        return "\n".join(lines)


@dataclass(frozen=True)
class AttributeExtractionResult:
    """Attribute-enriched dataframe and associated extraction report."""

    dataframe: pd.DataFrame
    report: AttributeExtractionReport


class ProductAttributeExtractor:
    """Extract high-confidence structured attributes from canonical product metadata."""

    def extract(self, dataframe: pd.DataFrame) -> AttributeExtractionResult:
        """Return an attribute-enriched copy without modifying canonical columns."""
        logger = get_logger(__name__)

        if not isinstance(dataframe, pd.DataFrame):
            msg = "Attribute extraction input must be a pandas DataFrame"
            raise DataAttributeError(msg)

        missing_columns = [
            column for column in REQUIRED_CANONICAL_COLUMNS if column not in dataframe.columns
        ]
        if missing_columns:
            msg = f"Missing required canonical columns for attribute extraction: {', '.join(missing_columns)}"
            raise DataAttributeError(msg)

        input_row_count = len(dataframe)
        enriched = dataframe.copy(deep=True)
        normalized_descriptions = enriched[ATTRIBUTE_TEXT_COLUMN].map(normalize_attribute_text)

        matched_row_counts: dict[str, int] = {}
        unmatched_row_counts: dict[str, int] = {}

        for attribute in ATTRIBUTE_DEFINITIONS:
            extract_value = partial(extract_attribute_value, attribute=attribute)
            extracted = normalized_descriptions.map(extract_value)
            series = extracted.astype("string")
            enriched[attribute.name] = series
            matched_row_counts[attribute.name] = int(series.notna().sum())
            unmatched_row_counts[attribute.name] = int(series.isna().sum())

        output_row_count = len(enriched)
        if output_row_count != input_row_count:
            msg = (
                f"Attribute extraction row count mismatch: input={input_row_count}, "
                f"output={output_row_count}"
            )
            raise DataAttributeError(msg)

        if not enriched.index.equals(dataframe.index):
            msg = "Attribute extraction must preserve dataframe row order"
            raise DataAttributeError(msg)

        for column in REQUIRED_CANONICAL_COLUMNS:
            if not enriched[column].equals(dataframe[column]):
                msg = f"Attribute extraction modified canonical column: {column}"
                raise DataAttributeError(msg)

        report = AttributeExtractionReport(
            input_row_count=input_row_count,
            output_row_count=output_row_count,
            attributes_added=ATTRIBUTE_COLUMN_ORDER,
            matched_row_counts=matched_row_counts,
            unmatched_row_counts=unmatched_row_counts,
            row_count_preserved=output_row_count == input_row_count,
            row_order_preserved=enriched.index.equals(dataframe.index),
        )

        logger.info(
            "Extracted ProductIQ attributes for %s rows (%s attributes added)",
            report.output_row_count,
            len(report.attributes_added),
        )
        return AttributeExtractionResult(dataframe=enriched, report=report)
