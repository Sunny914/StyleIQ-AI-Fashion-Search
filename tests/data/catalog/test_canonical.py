"""Tests for ProductIQ canonical product schema building."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pandas as pd
import pytest

from data.catalog import (
    AJIO_SOURCE_NAME,
    CANONICAL_COLUMN_COUNT,
    CANONICAL_COLUMN_ORDER,
    AjioCanonicalProductBuilder,
)
from data.deduplication import AjioDataDeduplicator
from data.ingestion import AjioDataLoader
from data.preprocessing import (
    BRAND_NORMALIZED_COLUMN,
    COLOR_IS_CODED_COLUMN,
    COLOR_NORMALIZED_COLUMN,
    PRICE_ANOMALY_COLUMN,
    AjioDataCleaner,
    AjioDataNormalizer,
)
from productiq.exceptions import DataCatalogError, ProductIQError

PROJECT_ROOT = Path(__file__).resolve().parents[3]
AJIO_DATASET_PATH = PROJECT_ROOT / "resources" / "raw" / "Ajio Fashion Clothing.csv"


@pytest.fixture
def builder() -> AjioCanonicalProductBuilder:
    return AjioCanonicalProductBuilder()


def make_prepared_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "Product_URL": "https://example.com/a",
        "Brand": "puma",
        "Description": "Shirt",
        "Id_Product": "123456789001",
        "URL_image": "https://example.com/img-a",
        "Category_by_gender": "Men",
        "Discount Price (in Rs.)": 559,
        "Original Price (in Rs.)": 999,
        "Color": "darkblue",
        BRAND_NORMALIZED_COLUMN: "puma",
        COLOR_NORMALIZED_COLUMN: "dark_blue",
        COLOR_IS_CODED_COLUMN: False,
        PRICE_ANOMALY_COLUMN: False,
    }
    row.update(overrides)
    return row


def make_prepared_dataframe(rows: list[dict[str, object]] | None = None) -> pd.DataFrame:
    if rows is None:
        rows = [make_prepared_row()]
    dataframe = pd.DataFrame(rows)
    for column in ("Discount Price (in Rs.)", "Original Price (in Rs.)"):
        dataframe[column] = dataframe[column].astype("Int64")
    return dataframe


def test_valid_dataframe_builds_successfully(builder: AjioCanonicalProductBuilder) -> None:
    result = builder.build(make_prepared_dataframe())

    assert len(result.dataframe) == 1


def test_exact_canonical_columns_are_produced(builder: AjioCanonicalProductBuilder) -> None:
    result = builder.build(make_prepared_dataframe())

    assert list(result.dataframe.columns) == list(CANONICAL_COLUMN_ORDER)


def test_canonical_column_order_is_correct(builder: AjioCanonicalProductBuilder) -> None:
    result = builder.build(make_prepared_dataframe())

    assert result.dataframe.columns.tolist()[0] == "product_id"
    assert result.dataframe.columns.tolist()[-1] == "source"


def test_source_to_canonical_mapping_is_correct(builder: AjioCanonicalProductBuilder) -> None:
    result = builder.build(make_prepared_dataframe([make_prepared_row()]))

    assert result.dataframe.loc[0, "product_id"] == "123456789001"
    assert result.dataframe.loc[0, "product_url"] == "https://example.com/a"
    assert result.dataframe.loc[0, "brand"] == "puma"
    assert result.dataframe.loc[0, "brand_normalized"] == "puma"
    assert result.dataframe.loc[0, "description"] == "Shirt"
    assert result.dataframe.loc[0, "image_url"] == "https://example.com/img-a"
    assert result.dataframe.loc[0, "category_gender"] == "Men"
    assert result.dataframe.loc[0, "color_raw"] == "darkblue"
    assert result.dataframe.loc[0, "color_normalized"] == "dark_blue"
    assert bool(result.dataframe.loc[0, "color_is_coded"]) is False
    assert result.dataframe.loc[0, "discount_price_inr"] == 559
    assert result.dataframe.loc[0, "original_price_inr"] == 999
    assert bool(result.dataframe.loc[0, "price_anomaly"]) is False


def test_product_id_uses_string_dtype(builder: AjioCanonicalProductBuilder) -> None:
    result = builder.build(make_prepared_dataframe())

    assert str(result.dataframe["product_id"].dtype) == "string"


def test_prices_use_int64(builder: AjioCanonicalProductBuilder) -> None:
    result = builder.build(make_prepared_dataframe())

    assert str(result.dataframe["discount_price_inr"].dtype) == "Int64"
    assert str(result.dataframe["original_price_inr"].dtype) == "Int64"


def test_boolean_fields_use_boolean_dtype(builder: AjioCanonicalProductBuilder) -> None:
    result = builder.build(make_prepared_dataframe([make_prepared_row(**{PRICE_ANOMALY_COLUMN: True})]))

    assert str(result.dataframe["color_is_coded"].dtype) == "boolean"
    assert str(result.dataframe["price_anomaly"].dtype) == "boolean"


def test_source_is_ajio(builder: AjioCanonicalProductBuilder) -> None:
    result = builder.build(make_prepared_dataframe())

    assert (result.dataframe["source"] == AJIO_SOURCE_NAME).all()


def test_product_id_must_be_unique(builder: AjioCanonicalProductBuilder) -> None:
    rows = [
        make_prepared_row(Id_Product="1"),
        make_prepared_row(Id_Product="1", Product_URL="https://example.com/b"),
    ]

    with pytest.raises(DataCatalogError, match="duplicate product_id"):
        builder.build(make_prepared_dataframe(rows))


def test_null_product_id_fails(builder: AjioCanonicalProductBuilder) -> None:
    with pytest.raises(DataCatalogError, match="null or empty product_id"):
        builder.build(make_prepared_dataframe([make_prepared_row(Id_Product=None)]))


def test_empty_product_id_fails(builder: AjioCanonicalProductBuilder) -> None:
    with pytest.raises(DataCatalogError, match="null or empty product_id"):
        builder.build(make_prepared_dataframe([make_prepared_row(Id_Product="   ")]))


def test_missing_source_column_fails(builder: AjioCanonicalProductBuilder) -> None:
    with pytest.raises(DataCatalogError, match="Missing required source columns"):
        builder.build(make_prepared_dataframe().drop(columns=["Brand"]))


def test_invalid_input_type_fails(builder: AjioCanonicalProductBuilder) -> None:
    with pytest.raises(DataCatalogError, match="pandas DataFrame"):
        builder.build(["invalid"])  # type: ignore[arg-type]


def test_row_count_is_preserved(builder: AjioCanonicalProductBuilder) -> None:
    rows = [make_prepared_row(Id_Product="1"), make_prepared_row(Id_Product="2")]
    result = builder.build(make_prepared_dataframe(rows))

    assert result.report.input_row_count == 2
    assert result.report.output_row_count == 2
    assert result.report.row_count_preserved is True


def test_input_dataframe_is_not_mutated(builder: AjioCanonicalProductBuilder) -> None:
    dataframe = make_prepared_dataframe()
    before = deepcopy(dataframe)

    builder.build(dataframe)

    pd.testing.assert_frame_equal(dataframe, before)


def test_source_values_are_preserved(builder: AjioCanonicalProductBuilder) -> None:
    prepared = make_prepared_dataframe(
        [
            make_prepared_row(Category_by_gender="Women"),
            make_prepared_row(Id_Product="2", Category_by_gender="Men"),
        ]
    )
    result = builder.build(prepared)

    assert result.dataframe["category_gender"].tolist() == ["Women", "Men"]


def test_normalized_values_are_preserved_exactly(builder: AjioCanonicalProductBuilder) -> None:
    prepared = make_prepared_dataframe(
        [make_prepared_row(Color="ltblue", **{COLOR_NORMALIZED_COLUMN: "lt_blue"})]
    )
    result = builder.build(prepared)

    assert result.dataframe.loc[0, "color_raw"] == "ltblue"
    assert result.dataframe.loc[0, "color_normalized"] == "lt_blue"


def test_price_anomaly_values_are_preserved(builder: AjioCanonicalProductBuilder) -> None:
    prepared = make_prepared_dataframe([make_prepared_row(**{PRICE_ANOMALY_COLUMN: True})])
    result = builder.build(prepared)

    assert bool(result.dataframe.loc[0, "price_anomaly"]) is True


def test_no_additional_rows_are_removed(builder: AjioCanonicalProductBuilder) -> None:
    prepared = make_prepared_dataframe(
        [make_prepared_row(Id_Product="1"), make_prepared_row(Id_Product="2")]
    )
    result = builder.build(prepared)

    assert len(result.dataframe) == len(prepared)


def test_canonical_output_has_exactly_14_columns(builder: AjioCanonicalProductBuilder) -> None:
    result = builder.build(make_prepared_dataframe())

    assert len(result.dataframe.columns) == CANONICAL_COLUMN_COUNT == 14


def test_data_catalog_error_inherits_from_productiq_error() -> None:
    error = DataCatalogError("catalog failed")

    assert isinstance(error, ProductIQError)


@pytest.mark.skipif(not AJIO_DATASET_PATH.is_file(), reason="AJIO raw dataset is unavailable")
def test_full_pipeline_canonical_integration(builder: AjioCanonicalProductBuilder) -> None:
    prepared = AjioDataDeduplicator().deduplicate(
        AjioDataNormalizer().normalize(
            AjioDataCleaner().clean(AjioDataLoader().load(AJIO_DATASET_PATH)).dataframe
        ).dataframe
    ).dataframe
    result = builder.build(prepared)

    assert result.report.input_row_count == 367_172
    assert result.report.output_row_count == 367_172
    assert len(result.dataframe.columns) == 14
    assert result.report.duplicate_product_id_count == 0
    assert result.report.null_product_id_count == 0
    assert (result.dataframe["source"] == AJIO_SOURCE_NAME).all()
    assert int(result.dataframe["price_anomaly"].sum()) == 4
