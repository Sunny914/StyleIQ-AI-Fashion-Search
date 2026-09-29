"""AJIO dataset validation rules."""

from __future__ import annotations

import re
from urllib.parse import urlparse

import pandas as pd

from data.ingestion.ajio import AJIO_COLUMNS
from data.validation.base import BaseDataValidator
from data.validation.results import (
    ValidationFinding,
    ValidationReport,
    ValidationSeverity,
    ValidationStatus,
)
from productiq.exceptions import DataValidationError
from productiq.logging import get_logger

AJIO_REQUIRED_COLUMNS = AJIO_COLUMNS
AJIO_ALLOWED_CATEGORIES = {"Women", "Men"}
AJIO_URL_COLUMNS = ("Product_URL", "URL_image")
AJIO_REQUIRED_VALUE_COLUMNS = AJIO_REQUIRED_COLUMNS
AJIO_PRICE_COLUMNS = ("Discount Price (in Rs.)", "Original Price (in Rs.)")

PRICE_FORMAT_PATTERN = re.compile(r"^\s*(?:\d{1,3}(?:,\d{3})*|\d+)\s*$")


def _parse_price_for_validation(value: str) -> int:
    """Parse a raw price string for validation-only comparisons."""
    normalized = value.strip().replace(",", "")
    return int(normalized)


def _is_missing_required_value(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and pd.isna(value):
        return True
    if isinstance(value, str):
        return value == "" or value.strip() == ""
    return True


def _is_valid_url(value: str) -> bool:
    parsed = urlparse(value.strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


class AjioDataValidator(BaseDataValidator):
    """Validate AJIO raw datasets without modifying them."""

    def validate(self, dataframe: pd.DataFrame) -> ValidationReport:
        """Run AJIO validation checks and return a structured report."""
        logger = get_logger(__name__)

        if not isinstance(dataframe, pd.DataFrame):
            msg = "Validation input must be a pandas DataFrame"
            raise DataValidationError(msg)

        original_values = dataframe.copy(deep=True)
        report = ValidationReport()

        self._validate_schema(dataframe, report)
        self._validate_identity(dataframe, report)
        self._validate_required_values(dataframe, report)
        self._validate_price_format(dataframe, report)
        self._validate_price_business_rules(dataframe, report)
        self._validate_category(dataframe, report)
        self._validate_url_structure(dataframe, report)
        self._validate_description(dataframe, report)
        self._validate_brand(dataframe, report)
        self._validate_color(dataframe, report)

        if not dataframe.equals(original_values):
            msg = "Validation must not mutate the input DataFrame"
            raise DataValidationError(msg)

        logger.info(
            "Completed AJIO validation with %s findings (%s failures, %s warnings)",
            len(report.findings),
            sum(1 for finding in report.findings if finding.status is ValidationStatus.FAIL),
            sum(1 for finding in report.findings if finding.status is ValidationStatus.WARNING),
        )
        return report

    def _validate_schema(self, dataframe: pd.DataFrame, report: ValidationReport) -> None:
        actual_columns = list(dataframe.columns)
        missing_columns = [
            column for column in AJIO_REQUIRED_COLUMNS if column not in actual_columns
        ]
        unexpected_columns = [
            column for column in actual_columns if column not in AJIO_REQUIRED_COLUMNS
        ]

        if missing_columns:
            report.add(
                ValidationFinding(
                    category="SCHEMA",
                    rule_name="required_columns",
                    status=ValidationStatus.FAIL,
                    severity=ValidationSeverity.ERROR,
                    message=f"Missing required columns: {', '.join(missing_columns)}",
                    affected_row_count=len(missing_columns),
                )
            )
            return

        if unexpected_columns:
            report.add(
                ValidationFinding(
                    category="SCHEMA",
                    rule_name="unexpected_columns",
                    status=ValidationStatus.FAIL,
                    severity=ValidationSeverity.ERROR,
                    message=f"Unexpected columns present: {', '.join(unexpected_columns)}",
                    affected_row_count=len(unexpected_columns),
                )
            )
            return

        if len(actual_columns) != len(AJIO_REQUIRED_COLUMNS):
            report.add(
                ValidationFinding(
                    category="SCHEMA",
                    rule_name="column_count",
                    status=ValidationStatus.FAIL,
                    severity=ValidationSeverity.ERROR,
                    message=(
                        f"Expected {len(AJIO_REQUIRED_COLUMNS)} columns, "
                        f"found {len(actual_columns)}"
                    ),
                )
            )
            return

        report.add(
            ValidationFinding(
                category="SCHEMA",
                rule_name="schema",
                status=ValidationStatus.PASS,
                severity=ValidationSeverity.INFO,
                message="Required schema is present",
            )
        )

    def _validate_identity(self, dataframe: pd.DataFrame, report: ValidationReport) -> None:
        if dataframe.empty:
            report.add(
                ValidationFinding(
                    category="IDENTITY",
                    rule_name="non_empty",
                    status=ValidationStatus.FAIL,
                    severity=ValidationSeverity.ERROR,
                    message="Dataset is empty",
                    affected_row_count=0,
                )
            )
            return

        if "Id_Product" not in dataframe.columns:
            report.add(
                ValidationFinding(
                    category="IDENTITY",
                    rule_name="id_column",
                    status=ValidationStatus.FAIL,
                    severity=ValidationSeverity.ERROR,
                    message="Id_Product column is missing",
                )
            )
            return

        null_id_count = int(dataframe["Id_Product"].isna().sum())
        if null_id_count:
            report.add(
                ValidationFinding(
                    category="IDENTITY",
                    rule_name="id_nulls",
                    status=ValidationStatus.FAIL,
                    severity=ValidationSeverity.ERROR,
                    message="Id_Product contains null values",
                    affected_row_count=null_id_count,
                )
            )
            return

        duplicate_id_count = int(dataframe["Id_Product"].duplicated().sum())
        if duplicate_id_count:
            report.add(
                ValidationFinding(
                    category="IDENTITY",
                    rule_name="duplicate_ids",
                    status=ValidationStatus.FAIL,
                    severity=ValidationSeverity.ERROR,
                    message="Duplicate Id_Product values detected",
                    affected_row_count=duplicate_id_count,
                )
            )

        duplicate_row_count = int(dataframe.duplicated().sum())
        if duplicate_row_count:
            report.add(
                ValidationFinding(
                    category="IDENTITY",
                    rule_name="duplicate_rows",
                    status=ValidationStatus.FAIL,
                    severity=ValidationSeverity.ERROR,
                    message="Exact duplicate rows detected",
                    affected_row_count=duplicate_row_count,
                )
            )

        if duplicate_id_count or duplicate_row_count:
            return

        report.add(
            ValidationFinding(
                category="IDENTITY",
                rule_name="identity",
                status=ValidationStatus.PASS,
                severity=ValidationSeverity.INFO,
                message=(
                    f"{len(dataframe)} rows with {dataframe['Id_Product'].nunique()} unique IDs"
                ),
            )
        )

    def _validate_required_values(
        self,
        dataframe: pd.DataFrame,
        report: ValidationReport,
    ) -> None:
        invalid_counts: dict[str, int] = {}

        for column in AJIO_REQUIRED_VALUE_COLUMNS:
            if column not in dataframe.columns:
                continue
            invalid_count = int(dataframe[column].map(_is_missing_required_value).sum())
            if invalid_count:
                invalid_counts[column] = invalid_count

        if invalid_counts:
            affected_total = sum(invalid_counts.values())
            details = ", ".join(f"{column}={count}" for column, count in invalid_counts.items())
            report.add(
                ValidationFinding(
                    category="REQUIRED VALUES",
                    rule_name="required_values",
                    status=ValidationStatus.FAIL,
                    severity=ValidationSeverity.ERROR,
                    message=f"Missing or blank required values detected ({details})",
                    affected_row_count=affected_total,
                )
            )
            return

        report.add(
            ValidationFinding(
                category="REQUIRED VALUES",
                rule_name="required_values",
                status=ValidationStatus.PASS,
                severity=ValidationSeverity.INFO,
                message="All required values are present",
            )
        )

    def _validate_price_format(self, dataframe: pd.DataFrame, report: ValidationReport) -> None:
        invalid_mask = pd.Series(False, index=dataframe.index)

        for column in AJIO_PRICE_COLUMNS:
            if column not in dataframe.columns:
                continue
            column_invalid = dataframe[column].map(
                lambda value: _is_missing_required_value(value)
                or not isinstance(value, str)
                or not PRICE_FORMAT_PATTERN.match(value)
            )
            invalid_mask = invalid_mask | column_invalid

        invalid_count = int(invalid_mask.sum())
        if invalid_count:
            report.add(
                ValidationFinding(
                    category="PRICE FORMAT",
                    rule_name="price_format",
                    status=ValidationStatus.FAIL,
                    severity=ValidationSeverity.ERROR,
                    message="Invalid raw price format detected",
                    affected_row_count=invalid_count,
                )
            )
            return

        report.add(
            ValidationFinding(
                category="PRICE FORMAT",
                rule_name="price_format",
                status=ValidationStatus.PASS,
                severity=ValidationSeverity.INFO,
                message="Price fields use valid raw string formats",
            )
        )

    def _validate_price_business_rules(
        self,
        dataframe: pd.DataFrame,
        report: ValidationReport,
    ) -> None:
        non_positive_rows = 0
        discount_greater_rows = 0

        for row_index, row in dataframe.iterrows():
            try:
                discount_price = _parse_price_for_validation(row["Discount Price (in Rs.)"])
                original_price = _parse_price_for_validation(row["Original Price (in Rs.)"])
            except (KeyError, TypeError, ValueError):
                continue

            if discount_price <= 0 or original_price <= 0:
                non_positive_rows += 1

            if discount_price > original_price:
                discount_greater_rows += 1

        if non_positive_rows:
            report.add(
                ValidationFinding(
                    category="PRICE BUSINESS RULES",
                    rule_name="positive_prices",
                    status=ValidationStatus.FAIL,
                    severity=ValidationSeverity.ERROR,
                    message="Non-positive prices detected",
                    affected_row_count=non_positive_rows,
                )
            )

        if discount_greater_rows:
            report.add(
                ValidationFinding(
                    category="PRICE BUSINESS RULES",
                    rule_name="discount_lte_original",
                    status=ValidationStatus.WARNING,
                    severity=ValidationSeverity.WARNING,
                    message="Rows where discount price is greater than original price",
                    affected_row_count=discount_greater_rows,
                )
            )

        if not non_positive_rows and not discount_greater_rows:
            report.add(
                ValidationFinding(
                    category="PRICE BUSINESS RULES",
                    rule_name="price_business_rules",
                    status=ValidationStatus.PASS,
                    severity=ValidationSeverity.INFO,
                    message="Price business rules satisfied",
                )
            )

    def _validate_category(self, dataframe: pd.DataFrame, report: ValidationReport) -> None:
        if "Category_by_gender" not in dataframe.columns:
            return

        unexpected_categories = sorted(
            {
                value
                for value in dataframe["Category_by_gender"].dropna().unique()
                if value not in AJIO_ALLOWED_CATEGORIES
            }
        )
        if unexpected_categories:
            unexpected_count = int(
                dataframe["Category_by_gender"].isin(unexpected_categories).sum()
            )
            report.add(
                ValidationFinding(
                    category="CATEGORY",
                    rule_name="allowed_categories",
                    status=ValidationStatus.WARNING,
                    severity=ValidationSeverity.WARNING,
                    message=(
                        "Unexpected category values detected: "
                        f"{', '.join(unexpected_categories)}"
                    ),
                    affected_row_count=unexpected_count,
                )
            )
            return

        report.add(
            ValidationFinding(
                category="CATEGORY",
                rule_name="category",
                status=ValidationStatus.PASS,
                severity=ValidationSeverity.INFO,
                message="Category values are within the expected source set",
            )
        )

    def _validate_url_structure(self, dataframe: pd.DataFrame, report: ValidationReport) -> None:
        invalid_mask = pd.Series(False, index=dataframe.index)

        for column in AJIO_URL_COLUMNS:
            if column not in dataframe.columns:
                continue
            column_invalid = dataframe[column].map(
                lambda value: _is_missing_required_value(value)
                or not isinstance(value, str)
                or not _is_valid_url(value)
            )
            invalid_mask = invalid_mask | column_invalid

        invalid_count = int(invalid_mask.sum())
        if invalid_count:
            report.add(
                ValidationFinding(
                    category="URL STRUCTURE",
                    rule_name="url_structure",
                    status=ValidationStatus.FAIL,
                    severity=ValidationSeverity.ERROR,
                    message="Malformed or missing URL values detected",
                    affected_row_count=invalid_count,
                )
            )
            return

        report.add(
            ValidationFinding(
                category="URL STRUCTURE",
                rule_name="url_structure",
                status=ValidationStatus.PASS,
                severity=ValidationSeverity.INFO,
                message="URL fields have valid structural format",
            )
        )

    def _validate_description(self, dataframe: pd.DataFrame, report: ValidationReport) -> None:
        if "Description" not in dataframe.columns:
            return

        invalid_count = int(dataframe["Description"].map(_is_missing_required_value).sum())
        if invalid_count:
            report.add(
                ValidationFinding(
                    category="DESCRIPTION",
                    rule_name="description",
                    status=ValidationStatus.FAIL,
                    severity=ValidationSeverity.ERROR,
                    message="Empty or missing descriptions detected",
                    affected_row_count=invalid_count,
                )
            )
            return

        report.add(
            ValidationFinding(
                category="DESCRIPTION",
                rule_name="description",
                status=ValidationStatus.PASS,
                severity=ValidationSeverity.INFO,
                message="Descriptions are present",
            )
        )

    def _validate_brand(self, dataframe: pd.DataFrame, report: ValidationReport) -> None:
        if "Brand" not in dataframe.columns:
            return

        invalid_count = int(dataframe["Brand"].map(_is_missing_required_value).sum())
        if invalid_count:
            report.add(
                ValidationFinding(
                    category="BRAND",
                    rule_name="brand",
                    status=ValidationStatus.FAIL,
                    severity=ValidationSeverity.ERROR,
                    message="Empty or missing brand values detected",
                    affected_row_count=invalid_count,
                )
            )
            return

        report.add(
            ValidationFinding(
                category="BRAND",
                rule_name="brand",
                status=ValidationStatus.PASS,
                severity=ValidationSeverity.INFO,
                message="Brand values are present",
            )
        )

    def _validate_color(self, dataframe: pd.DataFrame, report: ValidationReport) -> None:
        if "Color" not in dataframe.columns:
            return

        invalid_count = int(dataframe["Color"].map(_is_missing_required_value).sum())
        if invalid_count:
            report.add(
                ValidationFinding(
                    category="COLOR",
                    rule_name="color",
                    status=ValidationStatus.FAIL,
                    severity=ValidationSeverity.ERROR,
                    message="Empty or missing color values detected",
                    affected_row_count=invalid_count,
                )
            )
            return

        report.add(
            ValidationFinding(
                category="COLOR",
                rule_name="color",
                status=ValidationStatus.PASS,
                severity=ValidationSeverity.INFO,
                message="Color values are present",
            )
        )
