"""Lexical similarity via existing BM25 machinery (Phase 11.3)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from productiq.representation.lexical import build_structured_lexical_text
from productiq.representation.schema import ProductRepresentation
from productiq.retrieval.bm25 import BM25Scorer


def seed_lexical_text_for_similarity(seed_product: ProductRepresentation) -> str:
    """Deterministic seed lexical document used as the BM25 query side."""
    return build_structured_lexical_text(seed_product)


def compute_lexical_similarities(
    *,
    seed_product: ProductRepresentation,
    candidate_product_ids: Sequence[str],
    scorer: BM25Scorer,
) -> Mapping[str, float]:
    """Return native BM25 scores for seed lexical text against each candidate document."""
    lexical_text = seed_lexical_text_for_similarity(seed_product)
    if not lexical_text.strip() or not candidate_product_ids:
        return {}
    scored = scorer.score_lexical_query(
        lexical_text,
        candidate_product_ids=tuple(dict.fromkeys(candidate_product_ids)),
    )
    return {row.product_id: row.score for row in scored}


__all__ = [
    "compute_lexical_similarities",
    "seed_lexical_text_for_similarity",
]
