"""Tests for AJIO data cleaning."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pandas as pd
import pytest

from data.ingestion import AjioDataLoader
from data.ingestion.ajio import AJIO_COLUMNS
from data.preprocessing import PRICE_ANOMALY_COLUMN, AjioDataCleaner
from productiq.exceptions import DataCleaningError, ProductIQError

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
def cleaner() -> AjioDataCleaner:
    return AjioDataCleaner()


def make_dataframe(rows: list[dict[str, str]] | None = None, **overrides: str) -> pd.DataFrame:
    if rows is None:
        row = VALID_ROW.copy()
        row.update(overrides)
        rows = [row]
    return pd.DataFrame(rows, columns=AJIO_COLUMNS)


def test_surrounding_whitespace_is_removed(cleaner: AjioDataCleaner) -> None:
    result = cleaner.clean(
        make_dataframe(
            Brand="  puma  ",
            Color="  ltblue  ",
            Description="  Sample text  ",
        )
    )

    assert result.dataframe.loc[0, "Brand"] == "puma"
    assert result.dataframe.loc[0, "Color"] == "ltblue"
    assert result.dataframe.loc[0, "Description"] == "Sample text"
    assert result.report.values_stripped >= 3


def test_internal_semantic_values_are_preserved(cleaner: AjioDataCleaner) -> None:
    result = cleaner.clean(
        make_dataframe(
            Brand="U.S. Polo Assn.",
            Color="ltblue",
            Description="Men's cotton t-shirt - blue",
        )
    )

    assert result.dataframe.loc[0, "Brand"] == "U.S. Polo Assn."
    assert result.dataframe.loc[0, "Color"] == "ltblue"
    assert result.dataframe.loc[0, "Description"] == "Men's cotton t-shirt - blue"


def test_prices_are_converted_correctly(cleaner: AjioDataCleaner) -> None:
    result = cleaner.clean(make_dataframe(**{"Discount Price (in Rs.)": "559", "Original Price (in Rs.)": "999"}))

    assert result.dataframe.loc[0, "Discount Price (in Rs.)"] == 559
    assert result.dataframe.loc[0, "Original Price (in Rs.)"] == 999


def test_comma_separated_prices_are_converted(cleaner: AjioDataCleaner) -> None:
    result = cleaner.clean(
        make_dataframe(
            **{
                "Discount Price (in Rs.)": "1,499",
                "Original Price (in Rs.)": "230,800",
            }
        )
    )

    assert result.dataframe.loc[0, "Discount Price (in Rs.)"] == 1499
    assert result.dataframe.loc[0, "Original Price (in Rs.)"] == 230800


def test_prices_use_nullable_integer_dtype(cleaner: AjioDataCleaner) -> None:
    result = cleaner.clean(make_dataframe())

    assert str(result.dataframe["Discount Price (in Rs.)"].dtype) == "Int64"
    assert str(result.dataframe["Original Price (in Rs.)"].dtype) == "Int64"


def test_id_product_remains_unchanged(cleaner: AjioDataCleaner) -> None:
    result = cleaner.clean(make_dataframe(Id_Product="462983590001"))

    assert result.dataframe.loc[0, "Id_Product"] == "462983590001"
    assert result.dataframe["Id_Product"].dtype == object


def test_brand_semantic_values_remain_unchanged(cleaner: AjioDataCleaner) -> None:
    result = cleaner.clean(make_dataframe(Brand="Allen Solly"))

    assert result.dataframe.loc[0, "Brand"] == "Allen Solly"


def test_color_semantic_values_remain_unchanged(cleaner: AjioDataCleaner) -> None:
    result = cleaner.clean(make_dataframe(Color="navyblue"))

    assert result.dataframe.loc[0, "Color"] == "navyblue"


def test_category_values_remain_unchanged(cleaner: AjioDataCleaner) -> None:
    result = cleaner.clean(make_dataframe(Category_by_gender="Women"))

    assert result.dataframe.loc[0, "Category_by_gender"] == "Women"


def test_urls_remain_semantically_unchanged(cleaner: AjioDataCleaner) -> None:
    product_url = "https://www.ajio.com/p/123456789001"
    image_url = "/medias/sys_master/root/example.jpg"
    result = cleaner.clean(make_dataframe(Product_URL=product_url, URL_image=image_url))

    assert result.dataframe.loc[0, "Product_URL"] == product_url
    assert result.dataframe.loc[0, "URL_image"] == image_url


def test_description_text_remains_semantically_unchanged(cleaner: AjioDataCleaner) -> None:
    description = "Printed round neck T-shirt"
    result = cleaner.clean(make_dataframe(Description=description))

    assert result.dataframe.loc[0, "Description"] == description


def test_price_anomaly_false_for_normal_rows(cleaner: AjioDataCleaner) -> None:
    result = cleaner.clean(make_dataframe())

    assert not bool(result.dataframe.loc[0, PRICE_ANOMALY_COLUMN])


def test_price_anomaly_true_when_discount_greater_than_original(cleaner: AjioDataCleaner) -> None:
    result = cleaner.clean(
        make_dataframe(
            **{
                "Discount Price (in Rs.)": "15,695",
                "Original Price (in Rs.)": "15,694",
            }
        )
    )

    assert bool(result.dataframe.loc[0, PRICE_ANOMALY_COLUMN])
    assert result.report.price_anomalies_flagged == 1


def test_anomalous_prices_are_not_modified(cleaner: AjioDataCleaner) -> None:
    result = cleaner.clean(
        make_dataframe(
            **{
                "Discount Price (in Rs.)": "15,695",
                "Original Price (in Rs.)": "15,694",
            }
        )
    )

    assert result.dataframe.loc[0, "Discount Price (in Rs.)"] == 15695
    assert result.dataframe.loc[0, "Original Price (in Rs.)"] == 15694


def test_no_rows_are_removed(cleaner: AjioDataCleaner) -> None:
    rows = [
        VALID_ROW,
        {**VALID_ROW, "Id_Product": "123456789002", "Brand": "Allen Solly"},
    ]
    result = cleaner.clean(make_dataframe(rows))

    assert result.report.input_row_count == 2
    assert result.report.output_row_count == 2
    assert result.report.rows_removed == 0


def test_input_dataframe_is_not_mutated(cleaner: AjioDataCleaner) -> None:
    dataframe = make_dataframe(Brand="  puma  ")
    before = deepcopy(dataframe)

    cleaner.clean(dataframe)

    pd.testing.assert_frame_equal(dataframe, before)


def test_cleaning_report_contains_correct_counts(cleaner: AjioDataCleaner) -> None:
    result = cleaner.clean(
        make_dataframe(
            Brand="  puma  ",
            **{
                "Discount Price (in Rs.)": "1,499",
                "Original Price (in Rs.)": "2,499",
            },
        )
    )

    assert result.report.input_row_count == 1
    assert result.report.output_row_count == 1
    assert result.report.prices_converted == 2
    assert result.report.values_stripped >= 1
    assert "Input rows:" in result.report.summary()


def test_invalid_input_type_raises_data_cleaning_error(cleaner: AjioDataCleaner) -> None:
    with pytest.raises(DataCleaningError, match="pandas DataFrame"):
        cleaner.clean(["not", "a", "dataframe"])  # type: ignore[arg-type]


def test_data_cleaning_error_inherits_from_productiq_error() -> None:
    error = DataCleaningError("cleaning failed")

    assert isinstance(error, ProductIQError)


@pytest.mark.skipif(not AJIO_DATASET_PATH.is_file(), reason="AJIO raw dataset is unavailable")
def test_full_ajio_dataset_cleaning_integration() -> None:
    loader = AjioDataLoader()
    cleaner = AjioDataCleaner()

    raw_dataframe = loader.load(AJIO_DATASET_PATH)
    raw_before = deepcopy(raw_dataframe)
    result = cleaner.clean(raw_dataframe)

    assert result.report.input_row_count == 367_172
    assert result.report.output_row_count == 367_172
    assert result.report.rows_removed == 0
    assert result.report.price_anomalies_flagged == 4
    assert int(result.dataframe[PRICE_ANOMALY_COLUMN].sum()) == 4

    pd.testing.assert_frame_equal(raw_dataframe, raw_before)
    assert raw_dataframe.loc[1, "Original Price (in Rs.)"] == "1,499"
    assert result.dataframe.loc[1, "Original Price (in Rs.)"] == 1499

    anomalies = result.dataframe[result.dataframe[PRICE_ANOMALY_COLUMN]]
    assert len(anomalies) == 4
    assert set(anomalies["Id_Product"]) == {
        "462983590001",
        "462983595001",
        "462975646001",
        "461716717001",
    }
