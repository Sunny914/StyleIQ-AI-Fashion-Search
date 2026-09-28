"""Tests for canonical catalog → ProductRepresentation builder."""

from __future__ import annotations

from typing import Any

import pytest

from productiq.exceptions.base import ProductRepresentationError
from productiq.representation.builder import (
    build_product_representation,
    build_product_representations,
)


def test_correct_source_mapping(canonical_record: dict[str, Any]) -> None:
    rep = build_product_representation(canonical_record)
    assert rep.product_id == canonical_record["product_id"]
    assert rep.brand == canonical_record["brand"]
    assert rep.brand_normalized == canonical_record["brand_normalized"]
    assert rep.category_gender == canonical_record["category_gender"]
    assert rep.product_type == canonical_record["product_type"]


def test_color_normalized_maps_to_color(canonical_record: dict[str, Any]) -> None:
    rep = build_product_representation(canonical_record)
    assert rep.color == ["blue"]
    assert "color_raw" not in rep.model_dump()


def test_no_mutation_of_input(canonical_record: dict[str, Any]) -> None:
    snapshot = dict(canonical_record)
    build_product_representation(canonical_record)
    assert canonical_record == snapshot


def test_missing_values(canonical_record: dict[str, Any]) -> None:
    canonical_record["material"] = None
    canonical_record["style_attributes"] = ""
    rep = build_product_representation(canonical_record)
    assert rep.material is None
    assert rep.style_attributes is None


def test_multivalue_conversion(canonical_record: dict[str, Any]) -> None:
    rep = build_product_representation(canonical_record)
    assert rep.product_features == ["patch_pocket", "pocket"]


def test_product_id_preservation(canonical_record: dict[str, Any]) -> None:
    canonical_record["product_id"] = "unique-id-999"
    rep = build_product_representation(canonical_record)
    assert rep.product_id == "unique-id-999"


def test_invalid_product_id() -> None:
    with pytest.raises(ProductRepresentationError):
        build_product_representation({"product_id": "  ", "category_gender": "Men"})


def test_invalid_category() -> None:
    with pytest.raises(ProductRepresentationError):
        build_product_representation({"product_id": "1", "category_gender": "Kids"})


def test_batch_build(canonical_record: dict[str, Any]) -> None:
    second = dict(canonical_record)
    second["product_id"] = "2"
    reps = build_product_representations([canonical_record, second])
    assert len(reps) == 2
    assert reps[0].product_id != reps[1].product_id


def test_real_parquet_rows(processed_parquet_path) -> None:
    import pandas as pd

    sample = pd.read_parquet(processed_parquet_path, engine="pyarrow").head(50)
    records = sample.to_dict(orient="records")
    reps = build_product_representations(records)
    assert len(reps) == len(sample)
    assert {rep.product_id for rep in reps} == set(sample["product_id"])
