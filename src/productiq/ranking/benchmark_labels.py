"""Judgment adapters for ranking datasets (Phase 10.3)."""

from __future__ import annotations

from collections.abc import Iterable

from productiq.retrieval.evaluation.dataset import LexicalEvaluationQuery


def binary_relevance_labels_for_products(
    evaluation_query: LexicalEvaluationQuery,
    product_ids: Iterable[str],
) -> dict[str, int]:
    """Map product IDs to judged binary relevance without using retrieval ranks as labels."""
    relevant = set(evaluation_query.relevant_product_ids)
    return {product_id: (1 if product_id in relevant else 0) for product_id in product_ids}


__all__ = ["binary_relevance_labels_for_products"]
