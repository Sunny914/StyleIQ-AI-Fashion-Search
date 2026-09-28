"""Tests for ProductRepresentation serialization."""

from __future__ import annotations

import json
from typing import Any

from productiq.representation.builder import build_product_representation
from productiq.representation.serializers import (
    REPRESENTATION_FIELD_ORDER,
    representation_to_dict,
    representation_to_json,
)


def test_dict_output(canonical_record: dict[str, Any]) -> None:
    rep = build_product_representation(canonical_record)
    data = representation_to_dict(rep)
    assert list(data.keys()) == list(REPRESENTATION_FIELD_ORDER)
    assert data["product_id"] == rep.product_id
    assert data["color"] == rep.color


def test_json_compatible(canonical_record: dict[str, Any]) -> None:
    rep = build_product_representation(canonical_record)
    payload = representation_to_dict(rep)
    json.dumps(payload)


def test_stable_field_names() -> None:
    assert "color" in REPRESENTATION_FIELD_ORDER
    assert "color_normalized" not in REPRESENTATION_FIELD_ORDER


def test_none_handling() -> None:
    rep = build_product_representation(
        {"product_id": "1", "category_gender": "Men", "brand": None},
    )
    data = representation_to_dict(rep)
    assert data["brand"] is None
    assert data["material"] is None


def test_json_round_trip_keys(canonical_record: dict[str, Any]) -> None:
    rep = build_product_representation(canonical_record)
    text = representation_to_json(rep)
    parsed = json.loads(text)
    assert set(parsed.keys()) == set(REPRESENTATION_FIELD_ORDER)
