"""Deterministic product text rendering from ProductRepresentation (Phase 3.4)."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from productiq.representation.schema import ProductRepresentation

# Machine-token overrides (lowercase key → readable label fragment).
_READABLE_TOKEN_OVERRIDES: dict[str, str] = {
    "t_shirt": "T-Shirt",
    "co_ord": "Co-Ord",
}

# Stable segment order for deterministic product text.
SegmentRenderer = Callable[[ProductRepresentation], str | None]


def render_machine_token(token: str) -> str:
    """Render one ontology/catalog machine token as readable text."""
    normalized = token.strip().lower()
    if not normalized:
        return ""
    override = _READABLE_TOKEN_OVERRIDES.get(normalized)
    if override is not None:
        return override
    return " ".join(part.capitalize() for part in normalized.split("_") if part)


def render_scalar_value(value: str) -> str:
    """Render a scalar string (brand, category, product type) for display."""
    stripped = value.strip()
    if not stripped:
        return ""
    if "_" in stripped:
        return render_machine_token(stripped)
    return stripped.title()


def render_multivalue(values: Sequence[str]) -> str:
    """Render ordered multi-value attributes as a comma-separated phrase."""
    rendered = [render_machine_token(item) for item in values]
    rendered = [item for item in rendered if item]
    if not rendered:
        return ""
    return ", ".join(rendered)


def _brand_segment(representation: ProductRepresentation) -> str | None:
    raw = representation.brand if representation.brand is not None else representation.brand_normalized
    if raw is None:
        return None
    rendered = render_scalar_value(raw)
    return rendered or None


def _category_segment(representation: ProductRepresentation) -> str | None:
    rendered = render_scalar_value(representation.category_gender)
    return rendered or None


def _optional_scalar_segment(value: str | None) -> str | None:
    if value is None:
        return None
    rendered = render_scalar_value(value)
    return rendered or None


def _optional_multivalue_segment(values: list[str] | None) -> str | None:
    if values is None:
        return None
    rendered = render_multivalue(values)
    return rendered or None


_TEXT_SEGMENTS: tuple[tuple[str, SegmentRenderer], ...] = (
    ("Brand", _brand_segment),
    ("Category", _category_segment),
    ("Product Type", lambda r: _optional_scalar_segment(r.product_type)),
    ("Color", lambda r: _optional_multivalue_segment(r.color)),
    ("Pattern", lambda r: _optional_multivalue_segment(r.pattern)),
    ("Material", lambda r: _optional_multivalue_segment(r.material)),
    ("Fit", lambda r: _optional_multivalue_segment(r.fit)),
    ("Sleeve", lambda r: _optional_multivalue_segment(r.sleeve)),
    ("Neckline", lambda r: _optional_multivalue_segment(r.neckline)),
    ("Features", lambda r: _optional_multivalue_segment(r.product_features)),
    ("Style", lambda r: _optional_multivalue_segment(r.style_attributes)),
)


def build_product_text(representation: ProductRepresentation) -> str:
    """Build deterministic, human-readable product text from structured attributes."""
    clauses: list[str] = []
    for label, render_segment in _TEXT_SEGMENTS:
        value = render_segment(representation)
        if value is None:
            continue
        clauses.append(f"{label}: {value}")
    if not clauses:
        return ""
    return ". ".join(clauses) + "."


class ProductTextBuilder:
    """Stateless builder for product text (delegates to ``build_product_text``)."""

    @staticmethod
    def build(representation: ProductRepresentation) -> str:
        return build_product_text(representation)


__all__ = [
    "ProductTextBuilder",
    "build_product_text",
    "render_machine_token",
    "render_multivalue",
    "render_scalar_value",
]
