"""Tests for Phase 3.5 lexical/search representation."""

from __future__ import annotations

import re

from productiq.representation.lexical import (
    build_lexical_text,
    build_lexical_text_from_canonical,
    build_structured_lexical_text,
    normalize_lexical_description,
)
from productiq.representation.schema import ProductRepresentation
from productiq.representation.text import render_machine_token
from tests.database.catalog_fixtures import make_product_record


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


def test_basic_lexical_representation() -> None:
    text = build_lexical_text(
        _fully_populated(),
        description="Striped slim fit shirt with patch pocket",
    )
    assert "Nike" in text
    assert "Men" in text
    assert "Shirt" in text
    assert "Navy Blue" in text
    assert "Striped slim fit shirt with patch pocket" in text


def test_deterministic_output() -> None:
    rep = _fully_populated()
    first = build_lexical_text(rep, description="Classic cotton shirt")
    second = build_lexical_text(rep, description="Classic cotton shirt")
    assert first == second


def test_field_ordering() -> None:
    structured = build_structured_lexical_text(_fully_populated())
    assert structured.index("Nike") < structured.index("Men")
    assert structured.index("Men") < structured.index("Shirt")
    assert structured.index("Shirt") < structured.index("Navy Blue")
    assert structured.index("Navy Blue") < structured.index("Striped")
    assert structured.index("Striped") < structured.index("Cotton, Polyester")
    assert structured.index("Cotton, Polyester") < structured.index("Slim")
    assert structured.index("Slim") < structured.index("Full")
    assert structured.index("Full") < structured.index("Collared")
    assert structured.index("Collared") < structured.index("Button, Chest Pocket")
    assert structured.index("Button, Chest Pocket") < structured.index("Mid Rise")


def test_included_structured_fields() -> None:
    structured = build_structured_lexical_text(_fully_populated())
    assert "Nike" in structured
    assert "Shirt" in structured
    assert "Mid Rise" in structured


def test_excluded_metadata_fields() -> None:
    record = make_product_record(
        product_id="999",
        product_url="https://example.com/p/999",
        image_url="https://example.com/img/999",
        source="ajio",
        discount_price_inr=499,
        original_price_inr=999,
        price_anomaly=True,
        color_is_coded=True,
    )
    rep = ProductRepresentation(
        product_id=record["product_id"],
        category_gender=record["category_gender"],
        brand=record["brand"],
    )
    text = build_lexical_text_from_canonical(rep, record)
    assert "999" not in text
    assert "example.com" not in text
    assert "499" not in text
    assert "ajio" not in text.lower()


def test_description_inclusion() -> None:
    text = build_lexical_text(_fully_populated(), description="  Relaxed   fit   tee  ")
    assert "Relaxed fit tee" in text


def test_blank_description() -> None:
    assert build_lexical_text(_fully_populated(), description="   ") == build_structured_lexical_text(
        _fully_populated()
    )


def test_missing_description() -> None:
    assert build_lexical_text(_fully_populated(), description=None) == build_structured_lexical_text(
        _fully_populated()
    )


def test_missing_structured_fields() -> None:
    rep = ProductRepresentation(product_id="1", category_gender="Women")
    assert build_structured_lexical_text(rep) == "Women"


def test_multivalue_fields() -> None:
    rep = ProductRepresentation(
        product_id="1",
        category_gender="Men",
        material=["polyester", "cotton"],
        product_features=["zip", "pocket"],
    )
    structured = build_structured_lexical_text(rep)
    assert "Polyester, Cotton" in structured
    assert "Zip, Pocket" in structured


def test_token_rendering() -> None:
    rep = ProductRepresentation(
        product_id="1",
        category_gender="Men",
        product_type="t_shirt",
        color=["navy_blue"],
        product_features=["chest_pocket"],
        style_attributes=["a_line"],
    )
    structured = build_structured_lexical_text(rep)
    assert "T-Shirt" in structured
    assert "Navy Blue" in structured
    assert "Chest Pocket" in structured
    assert "A Line" in structured
    assert render_machine_token("self_design") == "Self Design"


def test_repeated_execution_identical() -> None:
    rep = _fully_populated()
    outputs = [build_lexical_text(rep, description="desc") for _ in range(5)]
    assert len(set(outputs)) == 1


def test_representation_not_mutated() -> None:
    rep = _fully_populated()
    snapshot = rep.model_dump()
    build_lexical_text(rep, description="desc")
    assert rep.model_dump() == snapshot


def test_canonical_record_not_mutated() -> None:
    record = make_product_record(description="  Patch   pocket shirt  ")
    snapshot = dict(record)
    rep = ProductRepresentation(
        product_id=record["product_id"],
        category_gender=record["category_gender"],
        brand=record["brand"],
    )
    build_lexical_text_from_canonical(rep, record)
    assert record == snapshot


def test_no_unknown_placeholders() -> None:
    text = build_lexical_text(_fully_populated(), description="Cotton shirt").lower()
    assert not re.search(r"\bunknown\b", text)
    assert not re.search(r"\bnone\b", text)


def test_brand_and_normalized_deduped() -> None:
    rep = ProductRepresentation(
        product_id="1",
        category_gender="Men",
        brand="puma",
        brand_normalized="puma",
    )
    structured = build_structured_lexical_text(rep)
    assert structured.count("Puma") == 1


def test_normalize_lexical_description() -> None:
    assert normalize_lexical_description("  hello   world  ") == "hello world"
    assert normalize_lexical_description(None) is None
    assert normalize_lexical_description("") is None
