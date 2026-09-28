"""Deterministic semantic document text for future embedding input (Phase 3.6)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from productiq.representation.lexical import normalize_lexical_description
from productiq.representation.schema import ProductRepresentation
from productiq.representation.text import build_product_text

# Labeled structured field order matches Phase 3.4 (`text.py`); Description is appended last.
SEMANTIC_FIELD_ORDER: tuple[str, ...] = (
    "Brand",
    "Category",
    "Product Type",
    "Color",
    "Pattern",
    "Material",
    "Fit",
    "Sleeve",
    "Neckline",
    "Features",
    "Style",
    "Description",
)


def _labeled_clauses(text: str) -> list[str]:
    """Split labeled product text into clause segments without trailing document period."""
    stripped = text.strip()
    if not stripped:
        return []
    stripped = stripped.removesuffix(".")
    return [clause.strip() for clause in stripped.split(". ") if clause.strip()]


def build_semantic_text(
    representation: ProductRepresentation,
    *,
    description: str | None = None,
) -> str:
    """Build contextual labeled semantic document text (no embedding generation)."""
    clauses = _labeled_clauses(build_product_text(representation))

    normalized_description = normalize_lexical_description(description)
    if normalized_description:
        clauses.append(f"Description: {normalized_description}")

    if not clauses:
        return ""
    return ". ".join(clauses) + "."


def build_semantic_text_from_canonical(
    representation: ProductRepresentation,
    canonical_record: Mapping[str, Any],
) -> str:
    """Build semantic text from structured representation and canonical description."""
    return build_semantic_text(
        representation,
        description=canonical_record.get("description"),
    )


class SemanticRepresentationBuilder:
    """Stateless builder for semantic product documents."""

    @staticmethod
    def build(
        representation: ProductRepresentation,
        *,
        description: str | None = None,
    ) -> str:
        return build_semantic_text(representation, description=description)


__all__ = [
    "SEMANTIC_FIELD_ORDER",
    "SemanticRepresentationBuilder",
    "build_semantic_text",
    "build_semantic_text_from_canonical",
]
