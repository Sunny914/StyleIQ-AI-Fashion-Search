"""Tests for Phase 3.7 metadata/filtering representation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from productiq.exceptions.base import ProductRepresentationError
from productiq.representation.filtering import (
    FilteringRepresentation,
    build_filtering_representation,
    build_filtering_representation_from_canonical,
    filtering_representation_to_dict,
)
from productiq.representation.schema import ProductRepresentation
from tests.database.catalog_fixtures import make_product_record


def _representation() -> ProductRepresentation:
    return ProductRepresentation(
        product_id="123",
        brand="nike",
        brand_normalized="nike",
        category_gender="Men",
        product_type="shirt",
        color=["navy_blue"],
        pattern=["striped"],
        material=["cotton", "polyester"],
        fit=["slim"],
        sleeve=None,
        neckline=None,
        product_features=["pocket"],
        style_attributes=None,
    )


def _commercial_kwargs() -> dict[str, object]:
    return {
        "source": "ajio",
        "color_raw": "navy",
        "color_is_coded": False,
        "discount_price_inr": 999,
        "original_price_inr": 1499,
        "price_anomaly": False,
    }


def test_complete_valid_representation() -> None:
    filtering = build_filtering_representation(_representation(), **_commercial_kwargs())
    assert filtering.product_id == "123"
    assert filtering.source == "ajio"
    assert filtering.material == ["cotton", "polyester"]
    assert filtering.discount_price_inr == 999


def test_required_fields() -> None:
    with pytest.raises(ValidationError):
        FilteringRepresentation(
            product_id="1",
            source="ajio",
            category_gender="Men",
            color_raw="blue",
            color_is_coded=False,
            discount_price_inr=1,
            original_price_inr=2,
        )


def test_optional_fields_nullable() -> None:
    rep = ProductRepresentation(product_id="1", category_gender="Women")
    filtering = build_filtering_representation(
        rep,
        source="ajio",
        color_raw="red",
        color_is_coded=False,
        discount_price_inr=100,
        original_price_inr=200,
        price_anomaly=False,
    )
    assert filtering.brand is None
    assert filtering.pattern is None


def test_price_fields_are_integers() -> None:
    filtering = build_filtering_representation(_representation(), **_commercial_kwargs())
    assert isinstance(filtering.discount_price_inr, int)
    assert isinstance(filtering.original_price_inr, int)


def test_price_anomaly_preserved() -> None:
    filtering = build_filtering_representation(
        _representation(),
        source="ajio",
        color_raw="blue",
        color_is_coded=False,
        discount_price_inr=1500,
        original_price_inr=999,
        price_anomaly=True,
    )
    assert filtering.price_anomaly is True
    assert filtering.discount_price_inr > filtering.original_price_inr


def test_brand_and_category() -> None:
    filtering = build_filtering_representation(_representation(), **_commercial_kwargs())
    assert filtering.brand == "nike"
    assert filtering.category_gender == "Men"


def test_product_type_and_color() -> None:
    filtering = build_filtering_representation(_representation(), **_commercial_kwargs())
    assert filtering.product_type == "shirt"
    assert filtering.color == ["navy_blue"]


def test_multivalue_attributes() -> None:
    filtering = build_filtering_representation(_representation(), **_commercial_kwargs())
    assert filtering.material == ["cotton", "polyester"]
    assert filtering.product_features == ["pocket"]


def test_none_semantics_not_empty_list() -> None:
    rep = ProductRepresentation(product_id="1", category_gender="Men")
    filtering = build_filtering_representation(
        rep,
        source="ajio",
        color_raw="x",
        color_is_coded=False,
        discount_price_inr=1,
        original_price_inr=2,
        price_anomaly=False,
    )
    assert filtering.material is None


def test_empty_multivalue_list_rejected() -> None:
    with pytest.raises(ValidationError):
        FilteringRepresentation(
            product_id="1",
            source="ajio",
            category_gender="Men",
            color_raw="blue",
            color_is_coded=False,
            color=[],
            discount_price_inr=1,
            original_price_inr=2,
            price_anomaly=False,
        )


def test_duplicate_multivalue_rejected() -> None:
    with pytest.raises(ValidationError):
        FilteringRepresentation(
            product_id="1",
            source="ajio",
            category_gender="Men",
            color_raw="blue",
            color_is_coded=False,
            material=["cotton", "cotton"],
            discount_price_inr=1,
            original_price_inr=2,
            price_anomaly=False,
        )


def test_deterministic_construction() -> None:
    rep = _representation()
    first = build_filtering_representation(rep, **_commercial_kwargs())
    second = build_filtering_representation(rep, **_commercial_kwargs())
    assert first == second


def test_canonical_record_not_mutated() -> None:
    record = make_product_record(price_anomaly=True, color_is_coded=True)
    snapshot = dict(record)
    build_filtering_representation_from_canonical(record)
    assert record == snapshot


def test_product_representation_not_mutated() -> None:
    rep = _representation()
    snapshot = rep.model_dump()
    build_filtering_representation(rep, **_commercial_kwargs())
    assert rep.model_dump() == snapshot


def test_coded_color_preserved() -> None:
    record = make_product_record(color_raw="C123", color_is_coded=True, color_normalized="coded_value")
    filtering = build_filtering_representation_from_canonical(record)
    assert filtering.color_is_coded is True
    assert filtering.color_raw == "C123"
    assert filtering.color == ["coded_value"]


def test_normalized_color_distinct_from_raw() -> None:
    record = make_product_record(color_raw="navy", color_normalized="navy_blue")
    filtering = build_filtering_representation_from_canonical(record)
    assert filtering.color_raw == "navy"
    assert filtering.color == ["navy_blue"]


def test_typed_representation() -> None:
    filtering = build_filtering_representation(_representation(), **_commercial_kwargs())
    assert isinstance(filtering, FilteringRepresentation)


def test_storage_independent_dict_export() -> None:
    filtering = build_filtering_representation(_representation(), **_commercial_kwargs())
    payload = filtering_representation_to_dict(filtering)
    assert list(payload.keys()) == list(filtering_representation_to_dict(filtering).keys())
    assert "product_url" not in payload
    assert "description" not in payload


def test_from_canonical_integration() -> None:
    record = make_product_record()
    filtering = build_filtering_representation_from_canonical(record)
    assert filtering.product_id == record["product_id"]
    assert filtering.source == record["source"]


def test_invalid_category_raises() -> None:
    rep = ProductRepresentation(product_id="1", category_gender="Unisex")
    with pytest.raises(ProductRepresentationError):
        build_filtering_representation(rep, **_commercial_kwargs())
