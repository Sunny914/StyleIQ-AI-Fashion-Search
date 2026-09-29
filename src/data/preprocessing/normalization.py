"""Dataset normalization for cleaned AJIO product data."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from data.ingestion.ajio import AJIO_COLUMNS
from data.preprocessing.cleaning import AJIO_PRICE_COLUMNS, PRICE_ANOMALY_COLUMN
from data.preprocessing.color_rules import is_coded_color, normalize_color_value
from productiq.exceptions import DataNormalizationError
from productiq.logging import get_logger

BRAND_NORMALIZED_COLUMN = "Brand_Normalized"
COLOR_NORMALIZED_COLUMN = "Color_Normalized"
COLOR_IS_CODED_COLUMN = "Color_Is_Coded"

REQUIRED_INPUT_COLUMNS = (
    *AJIO_COLUMNS,
    *AJIO_PRICE_COLUMNS,
    PRICE_ANOMALY_COLUMN,
)


@dataclass(frozen=True)
class NormalizationReport:
    """Summary of normalization transformations."""

    input_row_count: int
    output_row_count: int
    columns_normalized: tuple[str, ...]
    values_changed: int
    brand_values_normalized: int
    color_values_normalized: int
    category_values_normalized: int
    opaque_color_rows: int
    opaque_color_unique_values: int
    rows_removed: int

    def summary(self) -> str:
        """Return a human-readable normalization summary."""
        return "\n".join(
            [
                f"Input rows: {self.input_row_count}",
                f"Output rows: {self.output_row_count}",
                f"Rows removed: {self.rows_removed}",
                f"Columns added/normalized: {', '.join(self.columns_normalized)}",
                f"Values changed: {self.values_changed}",
                f"Brand values normalized: {self.brand_values_normalized}",
                f"Color values normalized: {self.color_values_normalized}",
                f"Category values normalized: {self.category_values_normalized}",
                f"Opaque color rows: {self.opaque_color_rows}",
                f"Opaque color unique values: {self.opaque_color_unique_values}",
            ]
        )


@dataclass(frozen=True)
class NormalizationResult:
    """Normalized dataset and associated report."""

    dataframe: pd.DataFrame
    report: NormalizationReport


@dataclass(frozen=True)
class NormalizationProfile:
    """Evidence summary used to justify normalization rules."""

    brand_unique_count: int
    brand_case_variant_groups: int
    category_values: tuple[str, ...]
    color_unique_count: int
    opaque_color_row_count: int
    opaque_color_unique_count: int
    sample_colors: tuple[str, ...]
    sample_opaque_colors: tuple[str, ...]
    sample_brands: tuple[str, ...]


def profile_normalization_candidates(dataframe: pd.DataFrame) -> NormalizationProfile:
    """Profile cleaned AJIO data to summarize normalization opportunities."""
    brands = dataframe["Brand"].astype(str)
    colors = dataframe["Color"].astype(str)
    lower_brand_groups = brands.groupby(brands.str.lower()).nunique()
    case_variant_groups = int((lower_brand_groups > 1).sum())

    opaque_mask = colors.map(is_coded_color)
    opaque_colors = colors[opaque_mask]

    return NormalizationProfile(
        brand_unique_count=int(brands.nunique()),
        brand_case_variant_groups=case_variant_groups,
        category_values=tuple(sorted(dataframe["Category_by_gender"].astype(str).unique())),
        color_unique_count=int(colors.nunique()),
        opaque_color_row_count=int(opaque_mask.sum()),
        opaque_color_unique_count=int(opaque_colors.nunique()),
        sample_colors=tuple(colors.value_counts().head(15).index.astype(str).tolist()),
        sample_opaque_colors=tuple(opaque_colors.value_counts().head(15).index.astype(str).tolist()),
        sample_brands=tuple(brands.value_counts().head(15).index.astype(str).tolist()),
    )


class AjioDataNormalizer:
    """Apply deterministic semantic normalization to cleaned AJIO data."""

    def normalize(self, dataframe: pd.DataFrame) -> NormalizationResult:
        """Return a normalized copy of ``dataframe`` and a structured report."""
        logger = get_logger(__name__)

        if not isinstance(dataframe, pd.DataFrame):
            msg = "Normalization input must be a pandas DataFrame"
            raise DataNormalizationError(msg)

        missing_columns = [
            column for column in REQUIRED_INPUT_COLUMNS if column not in dataframe.columns
        ]
        if missing_columns:
            msg = f"Missing required columns for normalization: {', '.join(missing_columns)}"
            raise DataNormalizationError(msg)

        input_row_count = len(dataframe)
        normalized = dataframe.copy(deep=True)

        brand_values_normalized = self._normalize_brand(normalized)
        color_values_normalized, opaque_color_rows, opaque_unique = self._normalize_color(
            normalized
        )

        values_changed = brand_values_normalized + color_values_normalized
        columns_normalized = (
            BRAND_NORMALIZED_COLUMN,
            COLOR_NORMALIZED_COLUMN,
            COLOR_IS_CODED_COLUMN,
        )

        report = NormalizationReport(
            input_row_count=input_row_count,
            output_row_count=len(normalized),
            columns_normalized=columns_normalized,
            values_changed=values_changed,
            brand_values_normalized=brand_values_normalized,
            color_values_normalized=color_values_normalized,
            category_values_normalized=0,
            opaque_color_rows=opaque_color_rows,
            opaque_color_unique_values=opaque_unique,
            rows_removed=0,
        )

        logger.info(
            "Normalized AJIO dataset: %s rows, %s color values changed, %s opaque rows",
            report.output_row_count,
            report.color_values_normalized,
            report.opaque_color_rows,
        )
        return NormalizationResult(dataframe=normalized, report=report)

    def _normalize_brand(self, dataframe: pd.DataFrame) -> int:
        """Create ``Brand_Normalized`` without changing source ``Brand`` values."""
        original_brand = dataframe["Brand"].copy()
        dataframe[BRAND_NORMALIZED_COLUMN] = original_brand
        return int((original_brand != dataframe[BRAND_NORMALIZED_COLUMN]).sum())

    def _normalize_color(self, dataframe: pd.DataFrame) -> tuple[int, int, int]:
        """Create color normalization columns while preserving source ``Color`` values."""
        normalized_values: list[str] = []
        coded_flags: list[bool] = []
        changed_count = 0

        for value in dataframe["Color"].astype(str):
            normalized, is_coded = normalize_color_value(value)
            normalized_values.append(normalized)
            coded_flags.append(is_coded)
            if not is_coded and normalized != value:
                changed_count += 1

        dataframe[COLOR_NORMALIZED_COLUMN] = normalized_values
        dataframe[COLOR_IS_CODED_COLUMN] = coded_flags

        opaque_rows = int(sum(coded_flags))
        opaque_unique = int(dataframe.loc[dataframe[COLOR_IS_CODED_COLUMN], "Color"].nunique())
        return changed_count, opaque_rows, opaque_unique
