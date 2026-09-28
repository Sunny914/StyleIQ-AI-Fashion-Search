"""Deterministic lexical/search text for future BM25 indexing (Phase 3.5)."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from typing import Any

from productiq.representation.schema import ProductRepresentation
from productiq.representation.text import (
    render_multivalue,
    render_scalar_value,
)

# Fixed structured field order for lexical documents (search-oriented, no metadata).


def normalize_lexical_description(description: str | None) -> str | None:
    """Conservatively normalize canonical description for lexical indexing."""
    if description is None:
        return None
    if isinstance(description, float) and math.isnan(description):
        return None
    if not isinstance(description, str):
        return None
    normalized = re.sub(r"\s+", " ", description.strip())
    return normalized or None


def _optional_lexical_scalar(value: str | None) -> str | None:
    if value is None:
        return None
    rendered = render_scalar_value(value)
    return rendered or None


def _optional_lexical_multivalue(values: list[str] | None) -> str | None:
    if values is None:
        return None
    rendered = render_multivalue(values)
    return rendered or None


def _lexical_brand_terms(representation: ProductRepresentation) -> str | None:
    rendered_terms: list[str] = []
    seen_lower: set[str] = set()
    for raw in (representation.brand, representation.brand_normalized):
        if raw is None:
            continue
        rendered = render_scalar_value(raw)
        if not rendered:
            continue
        key = rendered.casefold()
        if key in seen_lower:
            continue
        seen_lower.add(key)
        rendered_terms.append(rendered)
    if not rendered_terms:
        return None
    return " ".join(rendered_terms)


def _structured_lexical_parts(representation: ProductRepresentation) -> list[str]:
    field_renderers: tuple[tuple[str, str | None], ...] = (
        ("brand", _lexical_brand_terms(representation)),
        ("category_gender", _optional_lexical_scalar(representation.category_gender)),
        ("product_type", _optional_lexical_scalar(representation.product_type)),
        ("color", _optional_lexical_multivalue(representation.color)),
        ("pattern", _optional_lexical_multivalue(representation.pattern)),
        ("material", _optional_lexical_multivalue(representation.material)),
        ("fit", _optional_lexical_multivalue(representation.fit)),
        ("sleeve", _optional_lexical_multivalue(representation.sleeve)),
        ("neckline", _optional_lexical_multivalue(representation.neckline)),
        ("product_features", _optional_lexical_multivalue(representation.product_features)),
        ("style_attributes", _optional_lexical_multivalue(representation.style_attributes)),
    )
    parts: list[str] = []
    for _name, rendered in field_renderers:
        if rendered:
            parts.append(rendered)
    return parts


def build_structured_lexical_text(representation: ProductRepresentation) -> str:
    """Build searchable structured attribute text (no description, no metadata)."""
    return " ".join(_structured_lexical_parts(representation))


def build_lexical_text(
    representation: ProductRepresentation,
    *,
    description: str | None = None,
) -> str:
    """Build deterministic lexical/search document text for a product."""
    segments: list[str] = []
    structured = build_structured_lexical_text(representation)
    if structured:
        segments.append(structured)
    normalized_description = normalize_lexical_description(description)
    if normalized_description:
        segments.append(normalized_description)
    return " ".join(segments)


def build_lexical_text_from_canonical(
    representation: ProductRepresentation,
    canonical_record: Mapping[str, Any],
) -> str:
    """Build lexical text using structured representation plus canonical description."""
    description = canonical_record.get("description")
    return build_lexical_text(representation, description=description)


class LexicalRepresentationBuilder:
    """Stateless builder for lexical product documents."""

    @staticmethod
    def build(
        representation: ProductRepresentation,
        *,
        description: str | None = None,
    ) -> str:
        return build_lexical_text(representation, description=description)


__all__ = [
    "LexicalRepresentationBuilder",
    "build_lexical_text",
    "build_lexical_text_from_canonical",
    "build_structured_lexical_text",
    "normalize_lexical_description",
]
