"""Tests for Phase 3.6 semantic representation."""

from __future__ import annotations

import re

from productiq.representation.lexical import build_lexical_text
from productiq.representation.schema import ProductRepresentation
from productiq.representation.semantic import (
    SEMANTIC_FIELD_ORDER,
    build_semantic_text,
    build_semantic_text_from_canonical,
)
from productiq.representation.text import build_product_text
from tests.database.catalog_fixtures import make_product_record


def _fully_populated() -> ProductRepresentation:
    return ProductRepresentation(
        product_id="123",
        brand="roadster",
        brand_normalized="roadster",
        category_gender="Men",
        product_type="t_shirt",
        color=["navy_blue", "white"],
        pattern=["printed"],
        material=["cotton"],
        fit=["regular"],
        sleeve=None,
        neckline=None,
        product_features=None,
        style_attributes=None,
    )


def test_basic_semantic_representation() -> None:
    text = build_semantic_text(
        _fully_populated(),
        description="Lightweight cotton casual t-shirt suitable for everyday wear.",
    )
    assert "Brand: Roadster." in text
    assert "Category: Men." in text
    assert "Product Type: T-Shirt." in text
    assert "Color: Navy Blue, White." in text
    assert "Description: Lightweight cotton casual t-shirt suitable for everyday wear." in text


def test_exact_field_ordering() -> None:
    text = build_semantic_text(
        _fully_populated(),
        description="Everyday tee",
    )
    labels = [label for label in SEMANTIC_FIELD_ORDER if f"{label}:" in text]
    assert labels == [
        "Brand",
        "Category",
        "Product Type",
        "Color",
        "Pattern",
        "Material",
        "Fit",
        "Description",
    ]
    assert text.index("Brand:") < text.index("Category:")
    assert text.index("Category:") < text.index("Product Type:")
    assert text.index("Fit:") < text.index("Description:")


def test_brand_handling_deduped() -> None:
    rep = ProductRepresentation(
        product_id="1",
        brand="puma",
        brand_normalized="puma",
        category_gender="Women",
    )
    text = build_semantic_text(rep)
    assert text.count("Brand: Puma") == 1


def test_category_and_product_type() -> None:
    text = build_semantic_text(_fully_populated())
    assert "Category: Men." in text
    assert "Product Type: T-Shirt." in text


def test_multivalue_fields_preserve_order() -> None:
    rep = ProductRepresentation(
        product_id="1",
        category_gender="Men",
        color=["white", "navy_blue"],
        material=["polyester", "cotton"],
    )
    text = build_semantic_text(rep)
    assert "Color: White, Navy Blue." in text
    assert "Material: Polyester, Cotton." in text


def test_token_rendering() -> None:
    rep = ProductRepresentation(
        product_id="1",
        category_gender="Men",
        product_features=["chest_pocket"],
        style_attributes=["a_line"],
    )
    text = build_semantic_text(rep)
    assert "Features: Chest Pocket." in text
    assert "Style: A Line." in text


def test_description_inclusion() -> None:
    text = build_semantic_text(_fully_populated(), description="  Relaxed   fit   tee  ")
    assert "Description: Relaxed fit tee." in text


def test_missing_description() -> None:
    text = build_semantic_text(_fully_populated(), description=None)
    assert "Description:" not in text
    assert text == build_product_text(_fully_populated())


def test_blank_description() -> None:
    text = build_semantic_text(_fully_populated(), description="   ")
    assert "Description:" not in text


def test_missing_structured_fields() -> None:
    rep = ProductRepresentation(product_id="1", category_gender="Women")
    assert build_semantic_text(rep) == "Category: Women."


def test_deterministic_repeated_execution() -> None:
    rep = _fully_populated()
    desc = "Classic tee"
    assert build_semantic_text(rep, description=desc) == build_semantic_text(rep, description=desc)


def test_representation_not_mutated() -> None:
    rep = _fully_populated()
    snapshot = rep.model_dump()
    build_semantic_text(rep, description="desc")
    assert rep.model_dump() == snapshot


def test_canonical_record_not_mutated() -> None:
    record = make_product_record(description="  Patch   pocket shirt  ")
    snapshot = dict(record)
    rep = ProductRepresentation(
        product_id=record["product_id"],
        category_gender=record["category_gender"],
        brand=record["brand"],
    )
    build_semantic_text_from_canonical(rep, record)
    assert record == snapshot


def test_excluded_metadata_not_present() -> None:
    record = make_product_record(
        product_id="999",
        product_url="https://example.com/p/999",
        image_url="https://example.com/img/999",
        source="ajio",
        discount_price_inr=499,
        original_price_inr=999,
    )
    rep = ProductRepresentation(
        product_id=record["product_id"],
        category_gender=record["category_gender"],
        brand=record["brand"],
    )
    text = build_semantic_text_from_canonical(rep, record)
    assert "999" not in text.split("Description:")[0]
    assert "example.com" not in text
    assert "499" not in text
    assert "ajio" not in text.lower()


def test_no_unknown_placeholders() -> None:
    text = build_semantic_text(_fully_populated(), description="Cotton shirt").lower()
    assert not re.search(r"\bunknown\b", text)
    assert not re.search(r"\bnone\b", text)


def test_semantic_differs_from_lexical() -> None:
    rep = _fully_populated()
    description = "Lightweight cotton casual t-shirt suitable for everyday wear."
    semantic = build_semantic_text(rep, description=description)
    lexical = build_lexical_text(rep, description=description)
    assert semantic != lexical
    assert "Brand:" in semantic
    assert "Brand:" not in lexical
    assert "Description:" in semantic


def test_output_is_text_only() -> None:
    result = build_semantic_text(_fully_populated(), description="tee")
    assert isinstance(result, str)
