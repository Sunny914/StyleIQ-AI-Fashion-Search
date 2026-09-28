"""Tests for Phase 4.3 query representation for retrieval."""

from __future__ import annotations

import inspect

import pytest
from pydantic import ValidationError

from productiq.representation.dataset_schema import LEXICAL_TEXT_COLUMN, SEMANTIC_TEXT_COLUMN
from productiq.representation.query_contract import (
    QueryFilterConstraints,
    QueryRepresentation,
    build_query_representation,
    normalize_query_text,
)
from productiq.retrieval import (
    PRODUCT_FILTERING_RETRIEVAL_MODEL,
    PRODUCT_LEXICAL_RETRIEVAL_FIELD,
    PRODUCT_SEMANTIC_RETRIEVAL_FIELD,
    RETRIEVAL_PRODUCT_QUERY_ALIGNMENT,
    RETRIEVAL_QUERY_VIEW_FIELD_ORDER,
    RetrievalQueryView,
    build_retrieval_query_view,
    query_constraints_align_with_filtering_representation,
    retrieval_query_view_to_dict,
)


def test_product_query_retrieval_alignment_constants() -> None:
    assert PRODUCT_LEXICAL_RETRIEVAL_FIELD == LEXICAL_TEXT_COLUMN
    assert PRODUCT_SEMANTIC_RETRIEVAL_FIELD == SEMANTIC_TEXT_COLUMN
    assert PRODUCT_FILTERING_RETRIEVAL_MODEL == "FilteringRepresentation"
    assert RETRIEVAL_PRODUCT_QUERY_ALIGNMENT == (
        ("lexical_text", "lexical_intent"),
        ("semantic_text", "semantic_intent"),
        ("FilteringRepresentation", "constraints"),
    )


def test_query_constraints_align_with_filtering_representation() -> None:
    assert query_constraints_align_with_filtering_representation() is True


def test_retrieval_view_field_order_matches_model() -> None:
    assert RETRIEVAL_QUERY_VIEW_FIELD_ORDER == tuple(RetrievalQueryView.model_fields.keys())


def test_build_view_preserves_lexical_and_semantic_normalization() -> None:
    query = build_query_representation(
        "  black   Nike  running  shoes  under  ₹5000  ",
        lexical_text="  black nike running shoes  ",
        semantic_text="  Nike running shoes for athletic wear  ",
        constraints=QueryFilterConstraints(
            brand="Nike",
            max_discount_price_inr=5000,
            color=["black"],
        ),
    )
    view = build_retrieval_query_view(query)
    assert view.query_text == normalize_query_text(
        "  black   Nike  running  shoes  under  ₹5000  "
    )
    assert view.lexical_retrieval_text == "black nike running shoes"
    assert view.semantic_retrieval_text == "Nike running shoes for athletic wear"
    assert view.constraints == query.constraints


def test_women_floral_summer_dress_defaults_intents_to_query_text() -> None:
    query = build_query_representation("women floral summer dress")
    view = build_retrieval_query_view(query)
    assert view.lexical_retrieval_text == "women floral summer dress"
    assert view.semantic_retrieval_text == "women floral summer dress"
    assert view.constraints is None


def test_constraints_structured_and_unchanged() -> None:
    constraints = QueryFilterConstraints(
        category_gender="Women",
        color=["black"],
        max_discount_price_inr=3000,
    )
    query = build_query_representation("women's black floral dress under ₹3000", constraints=constraints)
    before = constraints.model_dump()
    view = build_retrieval_query_view(query)
    assert view.constraints == constraints
    assert constraints.model_dump() == before


def test_query_representation_not_mutated_by_view_projection() -> None:
    query = build_query_representation("nike shirt")
    snapshot = query.model_dump()
    _ = build_retrieval_query_view(query)
    assert query.model_dump() == snapshot


def test_retrieval_view_is_deterministic() -> None:
    query = build_query_representation("formal blue blazer")
    first = build_retrieval_query_view(query)
    second = build_retrieval_query_view(query)
    assert first == second


def test_retrieval_view_is_frozen() -> None:
    view = build_retrieval_query_view(build_query_representation("scarf"))
    with pytest.raises(ValidationError):
        view.lexical_retrieval_text = "other"  # type: ignore[misc]


def test_retrieval_view_serialization_stable() -> None:
    query = build_query_representation(
        "running shoes",
        constraints=QueryFilterConstraints(brand="Nike"),
    )
    payload = retrieval_query_view_to_dict(build_retrieval_query_view(query))
    assert list(payload.keys()) == list(RETRIEVAL_QUERY_VIEW_FIELD_ORDER)
    assert payload["constraints"]["brand"] == "Nike"


def test_build_retrieval_query_view_does_not_parse_raw_natural_language() -> None:
    source = inspect.getsource(build_retrieval_query_view)
    assert "normalize_query_text" not in source
    assert "re.sub" not in source


def test_retrieval_query_module_has_no_engine_or_embedding_imports() -> None:
    from productiq.retrieval import query_for_retrieval

    source = inspect.getsource(query_for_retrieval).lower()
    for token in ("bm25", "faiss", "sqlalchemy", "sentence_transformers", "openai", "pgvector"):
        assert token not in source


def test_existing_query_representation_remains_valid_type() -> None:
    query = build_query_representation("belt")
    assert isinstance(query, QueryRepresentation)
    assert build_retrieval_query_view(query).lexical_retrieval_text == query.lexical_intent.text
