"""Tests for multi-value parsing and representation validation."""

from __future__ import annotations

import math

import pytest

from productiq.exceptions.base import ProductRepresentationError
from productiq.representation.schema import ProductRepresentation
from productiq.representation.validators import (
    parse_pipe_delimited_multivalue,
    validate_category_gender,
    validate_product_representation,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, None),
        ("", None),
        ("   ", None),
        ("cotton", ["cotton"]),
        ("cotton|polyester", ["cotton", "polyester"]),
        ("cotton|polyester|cotton", ["cotton", "polyester"]),
        (" cotton | polyester ", ["cotton", "polyester"]),
        ("cotton|", ["cotton"]),
        ("cotton||polyester", ["cotton", "polyester"]),
        ("|cotton|", ["cotton"]),
    ],
)
def test_parse_pipe_delimited_multivalue(raw: object, expected: list[str] | None) -> None:
    assert parse_pipe_delimited_multivalue(raw) == expected


def test_parse_rejects_non_string() -> None:
    with pytest.raises(ProductRepresentationError):
        parse_pipe_delimited_multivalue(42)


def test_validate_category_gender_accepts_catalog_casing() -> None:
    validate_category_gender("Men")
    validate_category_gender("women")


def test_validate_category_gender_invalid() -> None:
    with pytest.raises(ProductRepresentationError):
        validate_category_gender("Unisex")


def test_validate_product_representation() -> None:
    rep = ProductRepresentation(product_id="1", category_gender="Men")
    validate_product_representation(rep)


def test_is_missing_value_nan() -> None:
    assert parse_pipe_delimited_multivalue(math.nan) is None
