"""Tests for AJIO data validation."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pandas as pd
import pytest

from data.ingestion import AjioDataLoader
from data.ingestion.ajio import AJIO_COLUMNS
from data.validation import AjioDataValidator, ValidationStatus
from data.validation.ajio import _parse_price_for_validation
from productiq.exceptions import DataValidationError, ProductIQError, ValidationError

PROJECT_ROOT = Path(__file__).resolve().parents[3]
AJIO_DATASET_PATH = PROJECT_ROOT / "resources" / "raw" / "Ajio Fashion Clothing.csv"

VALID_ROW = {
    "Product_URL": "https://www.ajio.com/p/123456789001",
    "Brand": "puma",
    "Description": "Sample product description",
    "Id_Product": "123456789001",
    "URL_image": "https://cdn.example.com/image.jpg",
    "Category_by_gender": "Men",
    "Discount Price (in Rs.)": "559",
    "Original Price (in Rs.)": "999",
    "Color": "white",
}


@pytest.fixture
def validator() -> AjioDataValidator:
    return AjioDataValidator()


def make_dataframe(rows: list[dict[str, str]] | None = None, **overrides: str) -> pd.DataFrame:
    if rows is None:
        row = VALID_ROW.copy()
        row.update(overrides)
        rows = [row]
    return pd.DataFrame(rows, columns=AJIO_COLUMNS)


def category_status(report, category: str) -> ValidationStatus | None:
    findings = report.findings_by_category(category)
    if not findings:
        return None
    if any(finding.status is ValidationStatus.FAIL for finding in findings):
        return ValidationStatus.FAIL
    if any(finding.status is ValidationStatus.WARNING for finding in findings):
        return ValidationStatus.WARNING
    return ValidationStatus.PASS


def test_valid_schema_passes(validator: AjioDataValidator) -> None:
    report = validator.validate(make_dataframe())

    assert category_status(report, "SCHEMA") is ValidationStatus.PASS


def test_missing_column_fails(validator: AjioDataValidator) -> None:
    dataframe = make_dataframe().drop(columns=["Brand"])

    report = validator.validate(dataframe)

    assert category_status(report, "SCHEMA") is ValidationStatus.FAIL


def test_unexpected_column_fails(validator: AjioDataValidator) -> None:
    dataframe = make_dataframe()
    dataframe["Extra_Column"] = "unexpected"

    report = validator.validate(dataframe)

    assert category_status(report, "SCHEMA") is ValidationStatus.FAIL


def test_empty_dataframe_fails(validator: AjioDataValidator) -> None:
    report = validator.validate(pd.DataFrame(columns=AJIO_COLUMNS))

    assert category_status(report, "IDENTITY") is ValidationStatus.FAIL


def test_duplicate_product_ids_fail(validator: AjioDataValidator) -> None:
    rows = [
        VALID_ROW,
        {**VALID_ROW, "Description": "Another description", "Color": "black"},
    ]
    report = validator.validate(make_dataframe(rows))

    assert category_status(report, "IDENTITY") is ValidationStatus.FAIL


def test_duplicate_rows_fail(validator: AjioDataValidator) -> None:
    rows = [VALID_ROW, VALID_ROW.copy()]
    report = validator.validate(make_dataframe(rows))

    findings = report.findings_by_category("IDENTITY")
    assert any(finding.rule_name == "duplicate_rows" for finding in findings)
    assert category_status(report, "IDENTITY") is ValidationStatus.FAIL


def test_null_values_fail(validator: AjioDataValidator) -> None:
    dataframe = make_dataframe()
    dataframe.loc[0, "Brand"] = None

    report = validator.validate(dataframe)

    assert category_status(report, "REQUIRED VALUES") is ValidationStatus.FAIL


def test_empty_strings_fail(validator: AjioDataValidator) -> None:
    report = validator.validate(make_dataframe(Brand=""))

    assert category_status(report, "REQUIRED VALUES") is ValidationStatus.FAIL


def test_whitespace_only_strings_fail(validator: AjioDataValidator) -> None:
    report = validator.validate(make_dataframe(Color="   "))

    assert category_status(report, "REQUIRED VALUES") is ValidationStatus.FAIL


@pytest.mark.parametrize(
    ("discount_price", "original_price"),
    [
        ("559", "999"),
        ("1,499", "2,300"),
        ("230,800", "230,800"),
        (" 999 ", "1,499"),
    ],
)
def test_valid_price_formats_pass(
    validator: AjioDataValidator,
    discount_price: str,
    original_price: str,
) -> None:
    report = validator.validate(
        make_dataframe(
            **{
                "Discount Price (in Rs.)": discount_price,
                "Original Price (in Rs.)": original_price,
            }
        )
    )

    assert category_status(report, "PRICE FORMAT") is ValidationStatus.PASS


@pytest.mark.parametrize(
    ("discount_price", "original_price"),
    [
        ("₹999", "1,499"),
        ("1,499.50", "2,000"),
        ("abc", "999"),
        ("999/-", "1,499"),
        ("unknown", "999"),
    ],
)
def test_invalid_price_formats_fail(
    validator: AjioDataValidator,
    discount_price: str,
    original_price: str,
) -> None:
    report = validator.validate(
        make_dataframe(
            **{
                "Discount Price (in Rs.)": discount_price,
                "Original Price (in Rs.)": original_price,
            }
        )
    )

    assert category_status(report, "PRICE FORMAT") is ValidationStatus.FAIL


def test_non_positive_prices_fail(validator: AjioDataValidator) -> None:
    report = validator.validate(
        make_dataframe(
            **{
                "Discount Price (in Rs.)": "0",
                "Original Price (in Rs.)": "999",
            }
        )
    )

    findings = report.findings_by_category("PRICE BUSINESS RULES")
    assert any(finding.rule_name == "positive_prices" for finding in findings)
    assert category_status(report, "PRICE BUSINESS RULES") is ValidationStatus.FAIL


def test_discount_greater_than_original_warns(validator: AjioDataValidator) -> None:
    report = validator.validate(
        make_dataframe(
            **{
                "Discount Price (in Rs.)": "15,695",
                "Original Price (in Rs.)": "15,694",
            }
        )
    )

    findings = report.findings_by_category("PRICE BUSINESS RULES")
    warning = next(finding for finding in findings if finding.rule_name == "discount_lte_original")
    assert warning.status is ValidationStatus.WARNING
    assert warning.affected_row_count == 1


def test_discount_equal_to_original_passes(validator: AjioDataValidator) -> None:
    report = validator.validate(
        make_dataframe(
            **{
                "Discount Price (in Rs.)": "999",
                "Original Price (in Rs.)": "999",
            }
        )
    )

    assert category_status(report, "PRICE BUSINESS RULES") is ValidationStatus.PASS


def test_unexpected_category_warns(validator: AjioDataValidator) -> None:
    report = validator.validate(make_dataframe(Category_by_gender="Kids"))

    assert category_status(report, "CATEGORY") is ValidationStatus.WARNING


def test_malformed_product_url_fails(validator: AjioDataValidator) -> None:
    report = validator.validate(make_dataframe(Product_URL="not-a-url"))

    assert category_status(report, "URL STRUCTURE") is ValidationStatus.FAIL


def test_malformed_url_image_fails(validator: AjioDataValidator) -> None:
    report = validator.validate(make_dataframe(URL_image="ftp://missing-scheme.example/image.jpg"))

    assert category_status(report, "URL STRUCTURE") is ValidationStatus.FAIL


def test_empty_description_fails(validator: AjioDataValidator) -> None:
    report = validator.validate(make_dataframe(Description=""))

    assert category_status(report, "DESCRIPTION") is ValidationStatus.FAIL


def test_empty_brand_fails(validator: AjioDataValidator) -> None:
    report = validator.validate(make_dataframe(Brand=""))

    assert category_status(report, "BRAND") is ValidationStatus.FAIL


def test_empty_color_fails(validator: AjioDataValidator) -> None:
    report = validator.validate(make_dataframe(Color="   "))

    assert category_status(report, "COLOR") is ValidationStatus.FAIL


def test_validation_does_not_mutate_dataframe(validator: AjioDataValidator) -> None:
    dataframe = make_dataframe()
    before = deepcopy(dataframe)

    validator.validate(dataframe)

    pd.testing.assert_frame_equal(dataframe, before)


def test_invalid_input_type_raises_data_validation_error(validator: AjioDataValidator) -> None:
    with pytest.raises(DataValidationError, match="pandas DataFrame"):
        validator.validate(["not", "a", "dataframe"])  # type: ignore[arg-type]


def test_data_validation_error_inherits_from_validation_error() -> None:
    error = DataValidationError("validation failed")

    assert isinstance(error, ValidationError)
    assert isinstance(error, ProductIQError)


def test_summary_contains_categories(validator: AjioDataValidator) -> None:
    report = validator.validate(make_dataframe())
    summary = report.summary()

    assert "SCHEMA" in summary
    assert "PRICE BUSINESS RULES" in summary


def test_parse_price_for_validation_handles_commas() -> None:
    assert _parse_price_for_validation("1,499") == 1499


@pytest.mark.skipif(not AJIO_DATASET_PATH.is_file(), reason="AJIO raw dataset is unavailable")
def test_full_ajio_dataset_validation_integration() -> None:
    loader = AjioDataLoader()
    validator = AjioDataValidator()

    dataframe = loader.load(AJIO_DATASET_PATH)
    before = deepcopy(dataframe)
    report = validator.validate(dataframe)

    assert category_status(report, "SCHEMA") is ValidationStatus.PASS
    assert category_status(report, "IDENTITY") is ValidationStatus.PASS
    assert category_status(report, "REQUIRED VALUES") is ValidationStatus.PASS
    assert category_status(report, "PRICE FORMAT") is ValidationStatus.PASS
    assert category_status(report, "CATEGORY") is ValidationStatus.PASS
    assert category_status(report, "URL STRUCTURE") is ValidationStatus.FAIL
    assert category_status(report, "DESCRIPTION") is ValidationStatus.PASS
    assert category_status(report, "BRAND") is ValidationStatus.PASS
    assert category_status(report, "COLOR") is ValidationStatus.PASS

    price_findings = report.findings_by_category("PRICE BUSINESS RULES")
    warning = next(
        finding for finding in price_findings if finding.rule_name == "discount_lte_original"
    )
    assert warning.status is ValidationStatus.WARNING
    assert warning.affected_row_count == 4

    url_findings = report.findings_by_category("URL STRUCTURE")
    url_failure = next(finding for finding in url_findings if finding.status is ValidationStatus.FAIL)
    assert url_failure.affected_row_count == 3

    assert report.has_warnings is True
    assert report.has_failures is True

    pd.testing.assert_frame_equal(dataframe, before)
