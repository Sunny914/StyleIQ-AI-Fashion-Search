"""Tests for attribute vocabulary profiling."""

from __future__ import annotations

import pandas as pd
import pytest

from data.attributes.profiler import ProductAttributeVocabularyProfiler
from data.catalog.schema import CANONICAL_COLUMN_ORDER
from productiq.exceptions import DataAttributeError


@pytest.fixture
def profiler() -> ProductAttributeVocabularyProfiler:
    return ProductAttributeVocabularyProfiler()


def make_canonical_row(**overrides: object) -> dict[str, object]:
    row = {column: pd.NA for column in CANONICAL_COLUMN_ORDER}
    row.update(
        {
            "product_id": "1",
            "product_url": "https://example.com/a",
            "brand": "puma",
            "brand_normalized": "puma",
            "description": "Striped Slim Fit Shirt with Patch Pocket",
            "image_url": "https://example.com/img",
            "category_gender": "Men",
            "color_raw": "blue",
            "color_normalized": "blue",
            "color_is_coded": False,
            "discount_price_inr": 100,
            "original_price_inr": 200,
            "price_anomaly": False,
            "source": "ajio",
        }
    )
    row.update(overrides)
    return row


def test_profiler_accepts_valid_canonical_dataframe(profiler: ProductAttributeVocabularyProfiler) -> None:
    dataframe = pd.DataFrame([make_canonical_row()])
    profile = profiler.profile(dataframe)

    assert profile.total_rows == 1
    assert profile.term_summaries


def test_profiler_invalid_input_type_fails(profiler: ProductAttributeVocabularyProfiler) -> None:
    with pytest.raises(DataAttributeError, match="pandas DataFrame"):
        profiler.profile(["invalid"])  # type: ignore[arg-type]


def test_profiler_missing_required_columns_fail(profiler: ProductAttributeVocabularyProfiler) -> None:
    dataframe = pd.DataFrame([make_canonical_row()]).drop(columns=["product_id"])

    with pytest.raises(DataAttributeError, match="Missing required canonical columns"):
        profiler.profile(dataframe)


def test_profiler_is_read_only(profiler: ProductAttributeVocabularyProfiler) -> None:
    dataframe = pd.DataFrame([make_canonical_row()])
    before = dataframe.copy()

    profiler.profile(dataframe)

    pd.testing.assert_frame_equal(dataframe, before)
