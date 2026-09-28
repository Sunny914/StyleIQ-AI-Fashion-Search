"""Tests for ProductRepresentation schema."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from productiq.representation.schema import ProductRepresentation


def test_valid_representation() -> None:
    rep = ProductRepresentation(
        product_id="123",
        brand="puma",
        brand_normalized="puma",
        category_gender="Men",
        product_type="shirt",
        color=["blue"],
        pattern=["striped"],
        material=None,
        fit=["slim"],
        sleeve=None,
        neckline=None,
        product_features=["pocket"],
        style_attributes=None,
    )
    assert rep.product_id == "123"
    assert rep.color == ["blue"]


def test_required_fields_missing() -> None:
    with pytest.raises(ValidationError):
        ProductRepresentation(category_gender="Men")  # type: ignore[call-arg]


def test_nullable_fields() -> None:
    rep = ProductRepresentation(product_id="1", category_gender="Women")
    assert rep.brand is None
    assert rep.material is None


def test_invalid_types() -> None:
    with pytest.raises(ValidationError):
        ProductRepresentation(
            product_id="1",
            category_gender="Men",
            color="blue",  # type: ignore[arg-type]
        )


def test_invalid_category_gender_empty() -> None:
    with pytest.raises(ValidationError):
        ProductRepresentation(product_id="1", category_gender="   ")


def test_multivalue_empty_list_rejected() -> None:
    with pytest.raises(ValidationError):
        ProductRepresentation(product_id="1", category_gender="Men", color=[])


def test_multivalue_duplicate_rejected() -> None:
    with pytest.raises(ValidationError):
        ProductRepresentation(
            product_id="1",
            category_gender="Men",
            material=["cotton", "cotton"],
        )


def test_extra_fields_forbidden() -> None:
    with pytest.raises(ValidationError):
        ProductRepresentation(
            product_id="1",
            category_gender="Men",
            color_raw="blue",  # type: ignore[call-arg]
        )
