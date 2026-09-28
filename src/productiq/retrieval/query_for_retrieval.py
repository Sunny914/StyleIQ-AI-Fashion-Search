"""Retrieval-facing projection of Phase 3.8 QueryRepresentation (Phase 4.3)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from productiq.representation.filtering import FilteringRepresentation
from productiq.representation.query_contract import (
    QUERY_TO_FILTERING_FACET_FIELDS,
    QUERY_TO_FILTERING_PRICE_BOUND_FIELDS,
    QueryFilterConstraints,
    QueryRepresentation,
)

# Product-side ↔ query-side retrieval alignment (mapping only; no execution).
PRODUCT_LEXICAL_RETRIEVAL_FIELD = "lexical_text"
PRODUCT_SEMANTIC_RETRIEVAL_FIELD = "semantic_text"
PRODUCT_FILTERING_RETRIEVAL_MODEL = FilteringRepresentation.__name__

QUERY_LEXICAL_RETRIEVAL_ATTRIBUTE = "lexical_intent"
QUERY_SEMANTIC_RETRIEVAL_ATTRIBUTE = "semantic_intent"
QUERY_FILTERING_RETRIEVAL_ATTRIBUTE = "constraints"

RETRIEVAL_PRODUCT_QUERY_ALIGNMENT: tuple[tuple[str, str], ...] = (
    (PRODUCT_LEXICAL_RETRIEVAL_FIELD, QUERY_LEXICAL_RETRIEVAL_ATTRIBUTE),
    (PRODUCT_SEMANTIC_RETRIEVAL_FIELD, QUERY_SEMANTIC_RETRIEVAL_ATTRIBUTE),
    (PRODUCT_FILTERING_RETRIEVAL_MODEL, QUERY_FILTERING_RETRIEVAL_ATTRIBUTE),
)

RETRIEVAL_QUERY_VIEW_FIELD_ORDER: tuple[str, ...] = (
    "query_text",
    "lexical_retrieval_text",
    "semantic_retrieval_text",
    "constraints",
)


class RetrievalQueryView(BaseModel):
    """Retrieval inputs derived from an understood query (not raw NL parsing)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    query_text: str
    lexical_retrieval_text: str
    semantic_retrieval_text: str
    constraints: QueryFilterConstraints | None = None


def build_retrieval_query_view(query: QueryRepresentation) -> RetrievalQueryView:
    """Project ``QueryRepresentation`` into lexical, semantic, and constraint retrieval inputs."""
    return RetrievalQueryView(
        query_text=query.query_text,
        lexical_retrieval_text=query.lexical_intent.text,
        semantic_retrieval_text=query.semantic_intent.text,
        constraints=query.constraints,
    )


def retrieval_query_view_to_dict(view: RetrievalQueryView) -> dict[str, Any]:
    """Serialize a retrieval query view to a JSON-compatible dict."""
    return view.model_dump(mode="json")


def query_has_usable_retrieval_intent(query: QueryRepresentation) -> bool:
    """True when lexical or semantic retrieval text is non-empty after strip."""
    return bool(query.lexical_intent.text.strip()) or bool(query.semantic_intent.text.strip())


def query_constraints_align_with_filtering_representation() -> bool:
    """Whether query constraint fields match the Phase 3.8 filtering alignment contract."""
    constraint_fields = set(QueryFilterConstraints.model_fields)
    expected = QUERY_TO_FILTERING_FACET_FIELDS | QUERY_TO_FILTERING_PRICE_BOUND_FIELDS
    return constraint_fields == expected


__all__ = [
    "PRODUCT_FILTERING_RETRIEVAL_MODEL",
    "PRODUCT_LEXICAL_RETRIEVAL_FIELD",
    "PRODUCT_SEMANTIC_RETRIEVAL_FIELD",
    "QUERY_FILTERING_RETRIEVAL_ATTRIBUTE",
    "QUERY_LEXICAL_RETRIEVAL_ATTRIBUTE",
    "QUERY_SEMANTIC_RETRIEVAL_ATTRIBUTE",
    "RETRIEVAL_PRODUCT_QUERY_ALIGNMENT",
    "RETRIEVAL_QUERY_VIEW_FIELD_ORDER",
    "RetrievalQueryView",
    "build_retrieval_query_view",
    "query_constraints_align_with_filtering_representation",
    "query_has_usable_retrieval_intent",
    "retrieval_query_view_to_dict",
]
