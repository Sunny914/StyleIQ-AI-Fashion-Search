"""Tests for AJIO data normalization."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pandas as pd
import pytest

from data.preprocessing import (
    BRAND_NORMALIZED_COLUMN,
    COLOR_IS_CODED_COLUMN,
    COLOR_NORMALIZED_COLUMN,
    PRICE_ANOMALY_COLUMN,
    AjioDataCleaner,
    AjioDataNormalizer,
    profile_normalization_candidates,
)
from data.preprocessing.color_rules import is_coded_color, normalize_color_value
from productiq.exceptions import DataNormalizationError, ProductIQError

PROJECT_ROOT = Path(__file__).resolve().parents[3]
AJIO_DATASET_PATH = PROJECT_ROOT / "resources" / "raw" / "Ajio Fashion Clothing.csv"

VALID_ROW = {
    "Product_URL": "https://www.ajio.com/p/123456789001",
    "Brand": "puma",
    "Description": "Sample product description",
    "Id_Product": "123456789001",
    "URL_image": "https://cdn.example.com/image.jpg",
    "Category_by_gender": "Men",
    "Discount Price (in Rs.)": 559,
    "Original Price (in Rs.)": 999,
    "Color": "darkblue",
    PRICE_ANOMALY_COLUMN: False,
}


@pytest.fixture
def normalizer() -> AjioDataNormalizer:
    return AjioDataNormalizer()


def make_cleaned_dataframe(**overrides: object) -> pd.DataFrame:
    row = VALID_ROW.copy()
    row.update(overrides)
    dataframe = pd.DataFrame([row])
    for column in ("Discount Price (in Rs.)", "Original Price (in Rs.)"):
        dataframe[column] = dataframe[column].astype("Int64")
    return dataframe


def test_normalizer_accepts_valid_dataframe(normalizer: AjioDataNormalizer) -> None:
    result = normalizer.normalize(make_cleaned_dataframe())

    assert len(result.dataframe) == 1
    assert COLOR_NORMALIZED_COLUMN in result.dataframe.columns


def test_missing_required_columns_raise(normalizer: AjioDataNormalizer) -> None:
    dataframe = make_cleaned_dataframe().drop(columns=["Brand"])

    with pytest.raises(DataNormalizationError, match="Missing required columns"):
        normalizer.normalize(dataframe)


def test_input_dataframe_is_not_mutated(normalizer: AjioDataNormalizer) -> None:
    dataframe = make_cleaned_dataframe(Color="ltblue")
    before = deepcopy(dataframe)

    normalizer.normalize(dataframe)

    pd.testing.assert_frame_equal(dataframe, before)


def test_original_brand_column_remains_unchanged(normalizer: AjioDataNormalizer) -> None:
    result = normalizer.normalize(make_cleaned_dataframe(Brand="Allen Solly"))

    assert result.dataframe.loc[0, "Brand"] == "Allen Solly"


def test_original_color_column_remains_unchanged(normalizer: AjioDataNormalizer) -> None:
    result = normalizer.normalize(make_cleaned_dataframe(Color="ltblue"))

    assert result.dataframe.loc[0, "Color"] == "ltblue"


def test_original_category_remains_unchanged(normalizer: AjioDataNormalizer) -> None:
    result = normalizer.normalize(make_cleaned_dataframe(Category_by_gender="Women"))

    assert result.dataframe.loc[0, "Category_by_gender"] == "Women"


def test_id_product_remains_unchanged(normalizer: AjioDataNormalizer) -> None:
    result = normalizer.normalize(make_cleaned_dataframe(Id_Product="462983590001"))

    assert result.dataframe.loc[0, "Id_Product"] == "462983590001"


def test_brand_normalized_matches_brand_when_no_case_variants(
    normalizer: AjioDataNormalizer,
) -> None:
    result = normalizer.normalize(make_cleaned_dataframe(Brand="puma"))

    assert result.dataframe.loc[0, BRAND_NORMALIZED_COLUMN] == "puma"
    assert result.report.brand_values_normalized == 0


def test_color_normalization_splits_supported_compounds(normalizer: AjioDataNormalizer) -> None:
    result = normalizer.normalize(make_cleaned_dataframe(Color="darkblue"))

    assert result.dataframe.loc[0, COLOR_NORMALIZED_COLUMN] == "dark_blue"
    assert result.report.color_values_normalized == 1


def test_opaque_colors_are_not_guessed(normalizer: AjioDataNormalizer) -> None:
    result = normalizer.normalize(make_cleaned_dataframe(Color="02dx"))

    assert result.dataframe.loc[0, "Color"] == "02dx"
    assert result.dataframe.loc[0, COLOR_NORMALIZED_COLUMN] == "02dx"
    assert bool(result.dataframe.loc[0, COLOR_IS_CODED_COLUMN]) is True


def test_category_values_remain_semantically_correct(normalizer: AjioDataNormalizer) -> None:
    result = normalizer.normalize(make_cleaned_dataframe(Category_by_gender="Men"))

    assert result.dataframe.loc[0, "Category_by_gender"] == "Men"
    assert result.report.category_values_normalized == 0


def test_description_is_not_transformed(normalizer: AjioDataNormalizer) -> None:
    description = "Men's round neck T-shirt"
    result = normalizer.normalize(make_cleaned_dataframe(Description=description))

    assert result.dataframe.loc[0, "Description"] == description


def test_urls_are_not_transformed(normalizer: AjioDataNormalizer) -> None:
    product_url = "https://www.ajio.com/p/123456789001"
    image_url = "/medias/sys_master/root/example.jpg"
    result = normalizer.normalize(
        make_cleaned_dataframe(Product_URL=product_url, URL_image=image_url)
    )

    assert result.dataframe.loc[0, "Product_URL"] == product_url
    assert result.dataframe.loc[0, "URL_image"] == image_url


def test_row_count_remains_unchanged(normalizer: AjioDataNormalizer) -> None:
    dataframe = pd.concat([make_cleaned_dataframe(), make_cleaned_dataframe(Id_Product="2")])
    result = normalizer.normalize(dataframe)

    assert result.report.input_row_count == 2
    assert result.report.output_row_count == 2


def test_normalized_columns_have_expected_names_and_types(normalizer: AjioDataNormalizer) -> None:
    result = normalizer.normalize(make_cleaned_dataframe(Color="greymelange"))

    assert result.dataframe[BRAND_NORMALIZED_COLUMN].dtype == object
    assert result.dataframe[COLOR_NORMALIZED_COLUMN].dtype == object
    assert result.dataframe[COLOR_IS_CODED_COLUMN].dtype == bool


def test_normalization_report_contains_accurate_counts(normalizer: AjioDataNormalizer) -> None:
    result = normalizer.normalize(make_cleaned_dataframe(Color="navyblue"))

    assert result.report.color_values_normalized == 1
    assert "Color values normalized:" in result.report.summary()


def test_price_columns_remain_unchanged(normalizer: AjioDataNormalizer) -> None:
    dataframe = make_cleaned_dataframe(
        **{
            "Discount Price (in Rs.)": 15695,
            "Original Price (in Rs.)": 15694,
            PRICE_ANOMALY_COLUMN: True,
        }
    )
    result = normalizer.normalize(dataframe)

    assert result.dataframe.loc[0, "Discount Price (in Rs.)"] == 15695
    assert result.dataframe.loc[0, "Original Price (in Rs.)"] == 15694


def test_price_anomaly_remains_unchanged(normalizer: AjioDataNormalizer) -> None:
    result = normalizer.normalize(make_cleaned_dataframe(**{PRICE_ANOMALY_COLUMN: True}))

    assert bool(result.dataframe.loc[0, PRICE_ANOMALY_COLUMN]) is True


def test_no_deduplication_occurs(normalizer: AjioDataNormalizer) -> None:
    duplicate_rows = pd.concat(
        [
            make_cleaned_dataframe(Id_Product="1"),
            make_cleaned_dataframe(Id_Product="2", Color="ltblue"),
        ]
    )
    result = normalizer.normalize(duplicate_rows)

    assert result.dataframe["Id_Product"].nunique() == 2


def test_no_rows_are_removed(normalizer: AjioDataNormalizer) -> None:
    result = normalizer.normalize(make_cleaned_dataframe())

    assert result.report.rows_removed == 0


def test_invalid_input_type_raises_data_normalization_error(normalizer: AjioDataNormalizer) -> None:
    with pytest.raises(DataNormalizationError, match="pandas DataFrame"):
        normalizer.normalize(["invalid"])  # type: ignore[arg-type]


def test_data_normalization_error_inherits_from_productiq_error() -> None:
    error = DataNormalizationError("normalization failed")

    assert isinstance(error, ProductIQError)


def test_normalize_color_value_maps_melange_without_guessing_codes() -> None:
    normalized, coded = normalize_color_value("greymelange")

    assert coded is False
    assert normalized == "grey_melange"

    opaque_normalized, opaque_coded = normalize_color_value("pg5")
    assert opaque_coded is True
    assert opaque_normalized == "pg5"


def test_is_coded_color_treats_digit_tokens_as_opaque() -> None:
    assert is_coded_color("02dx") is True
    assert is_coded_color("blue") is False


def test_mediumpink_normalizes_to_medium_pink() -> None:
    normalized, coded = normalize_color_value("mediumpink")

    assert coded is False
    assert normalized == "medium_pink"


def test_mediumpink_does_not_become_med_ium_pink() -> None:
    normalized, _coded = normalize_color_value("mediumpink")

    assert normalized != "med_ium_pink"


def test_darkgreymelanged_is_not_fabricated_melange_structure() -> None:
    normalized, coded = normalize_color_value("darkgreymelanged")

    assert coded is False
    assert normalized == "darkgreymelanged"
    assert "_melange" not in normalized


def test_greymelange_normalizes_to_grey_melange() -> None:
    normalized, coded = normalize_color_value("greymelange")

    assert coded is False
    assert normalized == "grey_melange"


def test_bluemelange_normalizes_to_blue_melange() -> None:
    normalized, coded = normalize_color_value("bluemelange")

    assert coded is False
    assert normalized == "blue_melange"


def test_lightgreymelange_normalizes_to_light_grey_melange() -> None:
    normalized, coded = normalize_color_value("lightgreymelange")

    assert coded is False
    assert normalized == "light_grey_melange"


def test_darkblue_navyblue_ltblue_compound_splits_remain_correct() -> None:
    assert normalize_color_value("darkblue") == ("dark_blue", False)
    assert normalize_color_value("navyblue") == ("navy_blue", False)
    assert normalize_color_value("ltblue") == ("lt_blue", False)


def test_coded_colors_remain_unchanged_after_color_rule_fixes() -> None:
    normalized, coded = normalize_color_value("02dx")

    assert coded is True
    assert normalized == "02dx"


@pytest.mark.skipif(not AJIO_DATASET_PATH.is_file(), reason="AJIO raw dataset is unavailable")
def test_full_ajio_dataset_normalization_integration() -> None:
    from data.ingestion import AjioDataLoader

    cleaned = AjioDataCleaner().clean(AjioDataLoader().load(AJIO_DATASET_PATH))
    cleaned_before = deepcopy(cleaned.dataframe)
    normalizer = AjioDataNormalizer()

    profile = profile_normalization_candidates(cleaned.dataframe)
    result = normalizer.normalize(cleaned.dataframe)

    assert profile.brand_case_variant_groups == 0
    assert profile.category_values == ("Men", "Women")
    assert result.report.input_row_count == 367_172
    assert result.report.output_row_count == 367_172
    assert result.report.rows_removed == 0
    assert result.report.brand_values_normalized == 0
    assert result.report.color_values_normalized > 0
    assert result.report.opaque_color_rows > 0
    assert int(result.dataframe[PRICE_ANOMALY_COLUMN].sum()) == 4

    pd.testing.assert_series_equal(
        cleaned_before["Id_Product"],
        result.dataframe["Id_Product"],
        check_names=True,
    )
    pd.testing.assert_series_equal(
        cleaned_before["Brand"],
        result.dataframe["Brand"],
        check_names=True,
    )
    pd.testing.assert_series_equal(
        cleaned_before["Color"],
        result.dataframe["Color"],
        check_names=True,
    )
    pd.testing.assert_series_equal(
        cleaned_before["Discount Price (in Rs.)"],
        result.dataframe["Discount Price (in Rs.)"],
        check_names=True,
    )
    pd.testing.assert_series_equal(
        cleaned_before[PRICE_ANOMALY_COLUMN],
        result.dataframe[PRICE_ANOMALY_COLUMN],
        check_names=True,
    )
