"""Tests for conservative AJIO deduplication."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pandas as pd
import pytest

from data.deduplication import DEDUPLICATION_POLICY_SUMMARY, AjioDataDeduplicator
from data.ingestion import AjioDataLoader
from data.preprocessing import (
    BRAND_NORMALIZED_COLUMN,
    COLOR_IS_CODED_COLUMN,
    COLOR_NORMALIZED_COLUMN,
    PRICE_ANOMALY_COLUMN,
    AjioDataCleaner,
    AjioDataNormalizer,
)
from productiq.exceptions import DataDeduplicationError

PROJECT_ROOT = Path(__file__).resolve().parents[3]
AJIO_DATASET_PATH = PROJECT_ROOT / "resources" / "raw" / "Ajio Fashion Clothing.csv"


@pytest.fixture
def deduplicator() -> AjioDataDeduplicator:
    return AjioDataDeduplicator()


def make_prepared_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "Product_URL": "https://example.com/a",
        "Brand": "puma",
        "Description": "Shirt",
        "Id_Product": "1",
        "URL_image": "https://example.com/img-a",
        "Category_by_gender": "Men",
        "Discount Price (in Rs.)": 100,
        "Original Price (in Rs.)": 200,
        "Color": "blue",
        BRAND_NORMALIZED_COLUMN: "puma",
        COLOR_NORMALIZED_COLUMN: "blue",
        COLOR_IS_CODED_COLUMN: False,
        PRICE_ANOMALY_COLUMN: False,
    }
    row.update(overrides)
    return row


def make_prepared_dataframe(rows: list[dict[str, object]]) -> pd.DataFrame:
    dataframe = pd.DataFrame(rows)
    for column in ("Discount Price (in Rs.)", "Original Price (in Rs.)"):
        dataframe[column] = dataframe[column].astype("Int64")
    return dataframe


def test_exact_duplicate_rows_are_removed(deduplicator: AjioDataDeduplicator) -> None:
    base = make_prepared_row(Id_Product="1")
    rows = [
        base,
        base.copy(),
        make_prepared_row(Id_Product="2", Product_URL="https://example.com/b"),
    ]
    result = deduplicator.deduplicate(make_prepared_dataframe(rows))

    assert result.report.input_row_count == 3
    assert result.report.output_row_count == 2
    assert result.report.rows_removed == 1


def test_first_exact_duplicate_occurrence_is_preserved(deduplicator: AjioDataDeduplicator) -> None:
    base = make_prepared_row(Id_Product="1", Description="Keep me")
    rows = [base, base.copy()]
    result = deduplicator.deduplicate(make_prepared_dataframe(rows))

    assert len(result.dataframe) == 1
    assert result.dataframe.iloc[0]["Description"] == "Keep me"


def test_id_product_duplicates_are_detected(deduplicator: AjioDataDeduplicator) -> None:
    rows = [
        make_prepared_row(Id_Product="1", Product_URL="https://example.com/a"),
        make_prepared_row(Id_Product="1", Product_URL="https://example.com/b"),
    ]

    with pytest.raises(DataDeduplicationError, match="Duplicate Id_Product"):
        deduplicator.deduplicate(make_prepared_dataframe(rows))


def test_id_product_duplicates_are_not_silently_dropped(deduplicator: AjioDataDeduplicator) -> None:
    dataframe = make_prepared_dataframe(
        [
            make_prepared_row(Id_Product="1", Product_URL="https://example.com/a"),
            make_prepared_row(Id_Product="1", Product_URL="https://example.com/b"),
        ]
    )

    with pytest.raises(DataDeduplicationError):
        deduplicator.deduplicate(dataframe)

    assert len(dataframe) == 2


def test_product_url_duplicates_are_preserved(deduplicator: AjioDataDeduplicator) -> None:
    rows = [
        make_prepared_row(Id_Product="1", Product_URL="https://example.com/shared"),
        make_prepared_row(
            Id_Product="2",
            Product_URL="https://example.com/shared",
            URL_image="https://example.com/img-b",
        ),
    ]
    result = deduplicator.deduplicate(make_prepared_dataframe(rows))

    assert len(result.dataframe) == 2
    assert result.dataframe["Product_URL"].nunique() == 1


def test_url_image_duplicates_are_preserved(deduplicator: AjioDataDeduplicator) -> None:
    rows = [
        make_prepared_row(Id_Product="1", URL_image="https://example.com/shared-image"),
        make_prepared_row(
            Id_Product="2",
            Product_URL="https://example.com/b",
            URL_image="https://example.com/shared-image",
        ),
    ]
    result = deduplicator.deduplicate(make_prepared_dataframe(rows))

    assert len(result.dataframe) == 2
    assert result.dataframe["URL_image"].nunique() == 1


def test_business_key_duplicates_are_preserved(deduplicator: AjioDataDeduplicator) -> None:
    rows = [
        make_prepared_row(Id_Product="1", Product_URL="https://example.com/a"),
        make_prepared_row(Id_Product="2", Product_URL="https://example.com/b"),
    ]
    result = deduplicator.deduplicate(make_prepared_dataframe(rows))

    assert len(result.dataframe) == 2


def test_input_dataframe_is_not_mutated(deduplicator: AjioDataDeduplicator) -> None:
    dataframe = make_prepared_dataframe([make_prepared_row(), make_prepared_row()])
    before = deepcopy(dataframe)

    deduplicator.deduplicate(dataframe)

    pd.testing.assert_frame_equal(dataframe, before)


def test_id_product_values_unchanged_for_preserved_rows(deduplicator: AjioDataDeduplicator) -> None:
    rows = [
        make_prepared_row(Id_Product="100"),
        make_prepared_row(Id_Product="200", Product_URL="https://example.com/b"),
    ]
    before_ids = [row["Id_Product"] for row in rows]
    result = deduplicator.deduplicate(make_prepared_dataframe(rows))

    assert result.dataframe["Id_Product"].tolist() == before_ids


def test_report_counts_are_accurate(deduplicator: AjioDataDeduplicator) -> None:
    result = deduplicator.deduplicate(
        make_prepared_dataframe([make_prepared_row(), make_prepared_row()])
    )

    assert result.report.exact_duplicate_rows_removed == 1
    assert result.report.exact_duplicate_rows_detected == 2
    assert result.report.duplicate_id_product_rows == 0
    assert DEDUPLICATION_POLICY_SUMMARY in result.report.policy_summary


@pytest.mark.skipif(not AJIO_DATASET_PATH.is_file(), reason="AJIO raw dataset is unavailable")
def test_full_ajio_dataset_is_no_op(deduplicator: AjioDataDeduplicator) -> None:
    prepared = AjioDataNormalizer().normalize(
        AjioDataCleaner().clean(AjioDataLoader().load(AJIO_DATASET_PATH)).dataframe
    ).dataframe
    before = deepcopy(prepared)
    result = deduplicator.deduplicate(prepared)

    assert result.report.input_row_count == 367_172
    assert result.report.output_row_count == 367_172
    assert result.report.rows_removed == 0
    assert result.report.exact_duplicate_rows_removed == 0
    pd.testing.assert_frame_equal(result.dataframe, before)


@pytest.mark.skipif(not AJIO_DATASET_PATH.is_file(), reason="AJIO raw dataset is unavailable")
def test_full_ajio_preserves_normalized_and_price_fields(deduplicator: AjioDataDeduplicator) -> None:
    prepared = AjioDataNormalizer().normalize(
        AjioDataCleaner().clean(AjioDataLoader().load(AJIO_DATASET_PATH)).dataframe
    ).dataframe
    result = deduplicator.deduplicate(prepared)

    assert int(result.dataframe[PRICE_ANOMALY_COLUMN].sum()) == 4
    pd.testing.assert_series_equal(result.dataframe["Color"], prepared["Color"])
    pd.testing.assert_series_equal(result.dataframe[COLOR_NORMALIZED_COLUMN], prepared[COLOR_NORMALIZED_COLUMN])
    pd.testing.assert_series_equal(
        result.dataframe["Discount Price (in Rs.)"],
        prepared["Discount Price (in Rs.)"],
    )
    pd.testing.assert_series_equal(result.dataframe["Product_URL"], prepared["Product_URL"])
    pd.testing.assert_series_equal(result.dataframe["URL_image"], prepared["URL_image"])
