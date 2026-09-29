"""Tests for deterministic product attribute extraction."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pandas as pd
import pytest

from data.attributes import MULTI_VALUE_DELIMITER, ProductAttributeExtractor
from data.attributes.rules import expression_matches, normalize_attribute_text
from data.catalog import AjioCanonicalProductBuilder
from data.catalog.schema import CANONICAL_COLUMN_ORDER
from data.deduplication import AjioDataDeduplicator
from data.ingestion import AjioDataLoader
from data.preprocessing import AjioDataCleaner, AjioDataNormalizer
from productiq.exceptions import DataAttributeError, ProductIQError

PROJECT_ROOT = Path(__file__).resolve().parents[3]
AJIO_DATASET_PATH = PROJECT_ROOT / "resources" / "raw" / "Ajio Fashion Clothing.csv"


@pytest.fixture
def extractor() -> ProductAttributeExtractor:
    return ProductAttributeExtractor()


def make_canonical_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "product_id": "123456789001",
        "product_url": "https://example.com/a",
        "brand": "puma",
        "brand_normalized": "puma",
        "description": "Striped Slim Fit Shirt with Patch Pocket",
        "image_url": "https://example.com/img",
        "category_gender": "Men",
        "color_raw": "blue",
        "color_normalized": "blue",
        "color_is_coded": False,
        "discount_price_inr": 559,
        "original_price_inr": 999,
        "price_anomaly": False,
        "source": "ajio",
    }
    row.update(overrides)
    return row


def make_canonical_dataframe(rows: list[dict[str, object]] | None = None) -> pd.DataFrame:
    if rows is None:
        rows = [{}]
    dataframe = pd.DataFrame([make_canonical_row(**row) for row in rows])
    for column in ("discount_price_inr", "original_price_inr"):
        dataframe[column] = dataframe[column].astype("Int64")
    for column in ("color_is_coded", "price_anomaly"):
        dataframe[column] = dataframe[column].astype("boolean")
    for column in CANONICAL_COLUMN_ORDER:
        if column not in ("discount_price_inr", "original_price_inr", "color_is_coded", "price_anomaly"):
            dataframe[column] = dataframe[column].astype("string")
    return dataframe


def test_valid_canonical_dataframe_is_accepted(extractor: ProductAttributeExtractor) -> None:
    result = extractor.extract(make_canonical_dataframe())

    assert len(result.dataframe) == 1


def test_invalid_input_type_fails(extractor: ProductAttributeExtractor) -> None:
    with pytest.raises(DataAttributeError, match="pandas DataFrame"):
        extractor.extract(["invalid"])  # type: ignore[arg-type]


def test_missing_required_canonical_columns_fail(extractor: ProductAttributeExtractor) -> None:
    with pytest.raises(DataAttributeError, match="Missing required canonical columns"):
        extractor.extract(make_canonical_dataframe().drop(columns=["product_id"]))


def test_product_row_count_is_preserved(extractor: ProductAttributeExtractor) -> None:
    dataframe = pd.concat(
        [
            make_canonical_dataframe(),
            make_canonical_dataframe([{"product_id": "2"}]),
        ],
        ignore_index=True,
    )
    result = extractor.extract(dataframe)

    assert result.report.input_row_count == 2
    assert result.report.output_row_count == 2


def test_product_row_order_is_preserved(extractor: ProductAttributeExtractor) -> None:
    dataframe = pd.concat(
        [
            make_canonical_dataframe([{"product_id": "1"}]),
            make_canonical_dataframe([{"product_id": "2"}]),
        ],
        ignore_index=True,
    )
    result = extractor.extract(dataframe)

    assert result.report.row_order_preserved is True
    assert result.dataframe["product_id"].tolist() == ["1", "2"]


def test_product_ids_are_unchanged(extractor: ProductAttributeExtractor) -> None:
    dataframe = make_canonical_dataframe()
    result = extractor.extract(dataframe)

    assert result.dataframe["product_id"].tolist() == dataframe["product_id"].tolist()


def test_existing_canonical_columns_are_unchanged(extractor: ProductAttributeExtractor) -> None:
    dataframe = make_canonical_dataframe()
    result = extractor.extract(dataframe)

    for column in CANONICAL_COLUMN_ORDER:
        assert result.dataframe[column].equals(dataframe[column])


def test_extraction_is_deterministic(extractor: ProductAttributeExtractor) -> None:
    dataframe = make_canonical_dataframe()
    first = extractor.extract(dataframe)
    second = extractor.extract(dataframe)

    assert first.dataframe.equals(second.dataframe)


def test_matching_is_case_insensitive(extractor: ProductAttributeExtractor) -> None:
    result = extractor.extract(
        make_canonical_dataframe([{"description": "SLIM FIT SHIRT WITH PATCH POCKET"}])
    )

    assert result.dataframe.loc[0, "fit"] == "slim_fit"


def test_matching_handles_normalized_whitespace(extractor: ProductAttributeExtractor) -> None:
    assert normalize_attribute_text("  Slim   Fit   Shirt  ") == "slim fit shirt"


def test_word_boundaries_prevent_obvious_false_positives() -> None:
    assert expression_matches("striped slim fit shirt", "top") is False
    assert expression_matches("crop top", "top") is True


def test_phrase_precedence_works(extractor: ProductAttributeExtractor) -> None:
    result = extractor.extract(
        make_canonical_dataframe([{"description": "Graphic T-Shirt"}])
    )

    assert result.dataframe.loc[0, "product_type"] == "t_shirt"


def test_multi_valued_attributes_are_deterministic(extractor: ProductAttributeExtractor) -> None:
    result = extractor.extract(
        make_canonical_dataframe([{"description": "Floral Printed Cotton Shirt"}])
    )

    assert result.dataframe.loc[0, "pattern"] == "floral|printed"
    assert result.dataframe.loc[0, "material"] == "cotton"


def test_multi_valued_attributes_contain_no_duplicates(extractor: ProductAttributeExtractor) -> None:
    result = extractor.extract(
        make_canonical_dataframe([{"description": "Printed Printed Shirt"}])
    )

    assert result.dataframe.loc[0, "pattern"] == "printed"


def test_multi_valued_attributes_use_documented_delimiter(extractor: ProductAttributeExtractor) -> None:
    result = extractor.extract(
        make_canonical_dataframe([{"description": "Striped Printed Shirt"}])
    )

    assert MULTI_VALUE_DELIMITER in result.dataframe.loc[0, "pattern"]


def test_unknown_attributes_become_na(extractor: ProductAttributeExtractor) -> None:
    result = extractor.extract(
        make_canonical_dataframe([{"description": "Accessory Item"}])
    )

    assert pd.isna(result.dataframe.loc[0, "product_type"])


def test_no_python_list_object_dtype_is_introduced(extractor: ProductAttributeExtractor) -> None:
    result = extractor.extract(make_canonical_dataframe())

    for column in result.report.attributes_added:
        assert str(result.dataframe[column].dtype) == "string"


def test_input_dataframe_is_not_mutated(extractor: ProductAttributeExtractor) -> None:
    dataframe = make_canonical_dataframe()
    before = deepcopy(dataframe)

    extractor.extract(dataframe)

    pd.testing.assert_frame_equal(dataframe, before)


def test_striped_slim_fit_shirt_example(extractor: ProductAttributeExtractor) -> None:
    result = extractor.extract(make_canonical_dataframe())

    row = result.dataframe.iloc[0]
    assert row["product_type"] == "shirt"
    assert row["fit"] == "slim_fit"
    assert row["pattern"] == "striped"
    assert row["product_features"] == "patch_pocket|pocket"


def test_tapered_fit_trousers_example(extractor: ProductAttributeExtractor) -> None:
    result = extractor.extract(
        make_canonical_dataframe([{"description": "Tapered Fit Flat-Front Trousers"}])
    )

    row = result.dataframe.iloc[0]
    assert row["product_type"] == "trousers"
    assert row["fit"] == "tapered_fit"
    assert row["style_attributes"] == "flat_front"


def test_data_attribute_error_inherits_from_productiq_error() -> None:
    error = DataAttributeError("attribute failed")

    assert isinstance(error, ProductIQError)


@pytest.mark.skipif(not AJIO_DATASET_PATH.is_file(), reason="AJIO raw dataset is unavailable")
def test_full_pipeline_attribute_extraction_integration(extractor: ProductAttributeExtractor) -> None:
    canonical = AjioCanonicalProductBuilder().build(
        AjioDataDeduplicator().deduplicate(
            AjioDataNormalizer().normalize(
                AjioDataCleaner().clean(AjioDataLoader().load(AJIO_DATASET_PATH)).dataframe
            ).dataframe
        ).dataframe
    ).dataframe
    result = extractor.extract(canonical)

    assert result.report.input_row_count == 367_172
    assert result.report.output_row_count == 367_172
    assert len(result.dataframe.columns) == len(CANONICAL_COLUMN_ORDER) + len(result.report.attributes_added)
    assert result.report.matched_row_counts["product_type"] > 0
