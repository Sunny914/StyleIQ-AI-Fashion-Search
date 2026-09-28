"""Tests for Phase 3.8 query-product representation contract."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from productiq.exceptions.base import ProductRepresentationError, QueryRepresentationError
from productiq.representation.query_contract import (
    QUERY_CONSTRAINT_EXCLUDED_PRODUCT_FIELDS,
    QUERY_TO_FILTERING_FACET_FIELDS,
    QUERY_TO_FILTERING_PRICE_BOUND_FIELDS,
    QueryFilterConstraints,
    QueryRepresentation,
    build_query_representation,
    normalize_query_text,
    query_representation_to_dict,
)


def test_constraint_field_alignment_with_filtering_contract() -> None:
    constraint_fields = set(QueryFilterConstraints.model_fields)
    assert QUERY_TO_FILTERING_FACET_FIELDS <= constraint_fields
    assert QUERY_TO_FILTERING_PRICE_BOUND_FIELDS <= constraint_fields
    assert constraint_fields == QUERY_TO_FILTERING_FACET_FIELDS | QUERY_TO_FILTERING_PRICE_BOUND_FIELDS
    assert not constraint_fields.intersection(QUERY_CONSTRAINT_EXCLUDED_PRODUCT_FIELDS)

def test_basic_query_representation() -> None:
    query = build_query_representation("  navy   nike  shirt  ")
    assert query.query_text == "navy nike shirt"
    assert query.lexical_intent.text == "navy nike shirt"
    assert query.semantic_intent.text == "navy nike shirt"
    assert query.constraints is None


def test_explicit_lexical_and_semantic_intent() -> None:
    query = build_query_representation(
        "nike shirt",
        lexical_text="nike shirt bm25",
        semantic_text="Brand: Nike. Product Type: Shirt.",
    )
    assert query.lexical_intent.text == "nike shirt bm25"
    assert query.semantic_intent.text == "Brand: Nike. Product Type: Shirt."


def test_constraints_optional_fields() -> None:
    constraints = QueryFilterConstraints(
        category_gender="Men",
        color=["navy_blue"],
        min_discount_price_inr=500,
        max_discount_price_inr=2000,
    )
    query = build_query_representation("shirt", constraints=constraints)
    assert query.constraints == constraints


def test_empty_query_rejected() -> None:
    with pytest.raises(QueryRepresentationError):
        normalize_query_text("   ")


def test_invalid_price_range_rejected() -> None:
    with pytest.raises(ValidationError):
        QueryFilterConstraints(min_discount_price_inr=2000, max_discount_price_inr=500)


def test_multivalue_constraint_validation() -> None:
    with pytest.raises(ValidationError):
        QueryFilterConstraints(material=["cotton", "cotton"])


def test_deterministic_build() -> None:
    first = build_query_representation("black t shirt")
    second = build_query_representation("black t shirt")
    assert first == second


def test_query_distinct_from_product_representations() -> None:
    query = build_query_representation("nike shirt")
    payload = query_representation_to_dict(query)
    assert isinstance(query, QueryRepresentation)
    assert "lexical_intent" in payload
    assert "product_id" not in payload


def test_no_mutation_of_constraints_object() -> None:
    constraints = QueryFilterConstraints(category_gender="Women")
    snapshot = constraints.model_dump()
    build_query_representation("dress", constraints=constraints)
    assert constraints.model_dump() == snapshot


def test_invalid_category_constraint_raises() -> None:
    constraints = QueryFilterConstraints(category_gender="Unisex")
    with pytest.raises(ProductRepresentationError):
        build_query_representation("dress", constraints=constraints)
