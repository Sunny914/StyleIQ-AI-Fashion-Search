"""Tests for Phase 3.4 product text representation."""

from __future__ import annotations

import re

from productiq.representation.schema import ProductRepresentation
from productiq.representation.text import (
    build_product_text,
    render_machine_token,
    render_multivalue,
)


def _fully_populated() -> ProductRepresentation:
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
        sleeve=["full"],
        neckline=["collared"],
        product_features=["button", "chest_pocket"],
        style_attributes=["mid_rise"],
    )


def test_fully_populated_product_text() -> None:
    text = build_product_text(_fully_populated())
    assert text.startswith("Brand: Nike.")
    assert "Category: Men." in text
    assert "Product Type: Shirt." in text
    assert "Color: Navy Blue." in text
    assert "Pattern: Striped." in text
    assert "Material: Cotton, Polyester." in text
    assert "Fit: Slim." in text
    assert "Sleeve: Full." in text
    assert "Neckline: Collared." in text
    assert "Features: Button, Chest Pocket." in text
    assert "Style: Mid Rise." in text
    assert text.endswith(".")


def test_many_missing_attributes() -> None:
    rep = ProductRepresentation(
        product_id="1",
        brand="puma",
        category_gender="Women",
        product_type="t_shirt",
        color=["black"],
    )
    text = build_product_text(rep)
    assert "Brand: Puma" in text
    assert "Product Type: T-Shirt" in text
    assert "Color: Black" in text
    assert "Material:" not in text
    assert "Pattern:" not in text
    assert "Features:" not in text


def test_only_required_fields() -> None:
    rep = ProductRepresentation(product_id="1", category_gender="Men")
    assert build_product_text(rep) == "Category: Men."


def test_multivalued_attributes_preserve_order() -> None:
    rep = ProductRepresentation(
        product_id="1",
        category_gender="Men",
        material=["polyester", "cotton", "viscose"],
        product_features=["zip", "pocket", "hood"],
    )
    text = build_product_text(rep)
    assert "Material: Polyester, Cotton, Viscose." in text
    assert "Features: Zip, Pocket, Hood." in text


def test_deterministic_repeated_generation() -> None:
    rep = _fully_populated()
    first = build_product_text(rep)
    second = build_product_text(rep)
    assert first == second


def test_no_empty_labels() -> None:
    rep = ProductRepresentation(
        product_id="1",
        category_gender="Men",
        brand="   ",
        brand_normalized=None,
        material=None,
    )
    text = build_product_text(rep)
    assert "Brand:" not in text
    assert "Material:" not in text


def test_no_unknown_placeholders() -> None:
    text = build_product_text(_fully_populated()).lower()
    assert not re.search(r"\bunknown\b", text)
    assert not re.search(r"\bnone\b", text)
    assert "no pattern" not in text


def test_readable_token_rendering() -> None:
    assert render_machine_token("navy_blue") == "Navy Blue"
    assert render_machine_token("three_quarter") == "Three Quarter"
    assert render_machine_token("t_shirt") == "T-Shirt"
    assert render_machine_token("chest_pocket") == "Chest Pocket"


def test_render_multivalue_joins_with_comma() -> None:
    assert render_multivalue(["cotton", "polyester"]) == "Cotton, Polyester"


def test_does_not_mutate_representation() -> None:
    rep = _fully_populated()
    snapshot = rep.model_dump()
    build_product_text(rep)
    assert rep.model_dump() == snapshot
