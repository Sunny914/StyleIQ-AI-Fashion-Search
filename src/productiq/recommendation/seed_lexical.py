"""Deterministic seed lexical text for recommendation BM25 generation (Phase 11.2)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from productiq.representation.lexical import build_lexical_text_from_canonical
from productiq.representation.schema import ProductRepresentation


def build_seed_lexical_text(
    seed_product: ProductRepresentation,
    *,
    canonical_record: Mapping[str, Any] | None = None,
) -> str:
    """Build BM25 query text from structured product fields (no user query)."""
    if canonical_record is None:
        return build_lexical_text_from_canonical(
            seed_product,
            {
                "description": None,
            },
        )
    return build_lexical_text_from_canonical(seed_product, canonical_record)


__all__ = ["build_seed_lexical_text"]
