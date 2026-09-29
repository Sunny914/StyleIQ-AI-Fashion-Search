"""Tests for read-only AJIO duplication profiling."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pandas as pd
import pytest

from data.deduplication import AjioDuplicationProfiler
from data.ingestion import AjioDataLoader
from data.preprocessing import AjioDataCleaner, AjioDataNormalizer
from data.preprocessing.normalization import COLOR_NORMALIZED_COLUMN
from productiq.exceptions import DataDeduplicationError, ProductIQError

PROJECT_ROOT = Path(__file__).resolve().parents[3]
AJIO_DATASET_PATH = PROJECT_ROOT / "resources" / "raw" / "Ajio Fashion Clothing.csv"


@pytest.fixture
def profiler() -> AjioDuplicationProfiler:
    return AjioDuplicationProfiler()


def make_prepared_dataframe(rows: list[dict[str, object]]) -> pd.DataFrame:
    dataframe = pd.DataFrame(rows)
    for column in ("Discount Price (in Rs.)", "Original Price (in Rs.)"):
        if column in dataframe.columns:
            dataframe[column] = dataframe[column].astype("Int64")
    if COLOR_NORMALIZED_COLUMN not in dataframe.columns and "Color" in dataframe.columns:
        dataframe[COLOR_NORMALIZED_COLUMN] = dataframe["Color"]
    if "price_anomaly" not in dataframe.columns:
        dataframe["price_anomaly"] = False
    return dataframe


def test_profiler_does_not_mutate_input(profiler: AjioDuplicationProfiler) -> None:
    dataframe = make_prepared_dataframe(
        [
            {
                "Product_URL": "https://example.com/a",
                "Brand": "puma",
                "Description": "Shirt",
                "Id_Product": "1",
                "URL_image": "https://example.com/img-a",
                "Category_by_gender": "Men",
                "Discount Price (in Rs.)": 100,
                "Original Price (in Rs.)": 200,
                "Color": "blue",
                COLOR_NORMALIZED_COLUMN: "blue",
                "price_anomaly": False,
            }
        ]
    )
    before = deepcopy(dataframe)

    profiler.profile(dataframe)

    pd.testing.assert_frame_equal(dataframe, before)


def test_exact_duplicate_detection(profiler: AjioDuplicationProfiler) -> None:
    row = {
        "Product_URL": "https://example.com/a",
        "Brand": "puma",
        "Description": "Shirt",
        "Id_Product": "1",
        "URL_image": "https://example.com/img-a",
        "Category_by_gender": "Men",
        "Discount Price (in Rs.)": 100,
        "Original Price (in Rs.)": 200,
        "Color": "blue",
        COLOR_NORMALIZED_COLUMN: "blue",
        "price_anomaly": False,
    }
    profile = profiler.profile(make_prepared_dataframe([row, row.copy()]))

    assert profile.exact_duplicate_rows == 1
    assert profile.exact_duplicate_groups == 1


def test_id_product_duplicate_detection(profiler: AjioDuplicationProfiler) -> None:
    row = {
        "Product_URL": "https://example.com/a",
        "Brand": "puma",
        "Description": "Shirt",
        "Id_Product": "1",
        "URL_image": "https://example.com/img-a",
        "Category_by_gender": "Men",
        "Discount Price (in Rs.)": 100,
        "Original Price (in Rs.)": 200,
        "Color": "blue",
        COLOR_NORMALIZED_COLUMN: "blue",
        "price_anomaly": False,
    }
    duplicate_id = {**row, "Product_URL": "https://example.com/b", "URL_image": "https://example.com/img-b"}
    profile = profiler.profile(make_prepared_dataframe([row, duplicate_id]))

    assert profile.id_product_duplicate_rows == 2
    assert profile.id_product_duplicate_values == 1


def test_candidate_key_profiling_is_deterministic(profiler: AjioDuplicationProfiler) -> None:
    rows = [
        {
            "Product_URL": "https://example.com/a",
            "Brand": "puma",
            "Description": "Shirt",
            "Id_Product": "1",
            "URL_image": "https://example.com/img-a",
            "Category_by_gender": "Men",
            "Discount Price (in Rs.)": 100,
            "Original Price (in Rs.)": 200,
            "Color": "blue",
            COLOR_NORMALIZED_COLUMN: "blue",
            "price_anomaly": False,
        },
        {
            "Product_URL": "https://example.com/b",
            "Brand": "puma",
            "Description": "Shirt",
            "Id_Product": "2",
            "URL_image": "https://example.com/img-b",
            "Category_by_gender": "Men",
            "Discount Price (in Rs.)": 100,
            "Original Price (in Rs.)": 200,
            "Color": "blue",
            COLOR_NORMALIZED_COLUMN: "blue",
            "price_anomaly": False,
        },
    ]
    first = profiler.profile(make_prepared_dataframe(rows))
    second = profiler.profile(make_prepared_dataframe(rows))

    assert first == second
    business_key = next(
        candidate
        for candidate in first.candidate_keys
        if candidate.key_name == "brand_description_category_color_prices"
    )
    assert business_key.duplicated_keys == 1
    assert business_key.rows_in_duplicated_groups == 2


def test_missing_required_columns_raise(profiler: AjioDuplicationProfiler) -> None:
    with pytest.raises(DataDeduplicationError, match="Missing required columns"):
        profiler.profile(pd.DataFrame({"Id_Product": ["1"]}))


def test_data_deduplication_error_inherits_from_productiq_error() -> None:
    error = DataDeduplicationError("deduplication failed")

    assert isinstance(error, ProductIQError)


@pytest.mark.skipif(not AJIO_DATASET_PATH.is_file(), reason="AJIO raw dataset is unavailable")
def test_full_ajio_duplication_profiling_integration(profiler: AjioDuplicationProfiler) -> None:
    prepared = AjioDataNormalizer().normalize(
        AjioDataCleaner().clean(AjioDataLoader().load(AJIO_DATASET_PATH)).dataframe
    ).dataframe
    before = deepcopy(prepared)
    profile = profiler.profile(prepared)

    assert profile.total_rows == 367_172
    assert profile.exact_duplicate_rows == 0
    assert profile.id_product_duplicate_rows == 0
    assert len(prepared) == 367_172
    pd.testing.assert_frame_equal(prepared, before)
