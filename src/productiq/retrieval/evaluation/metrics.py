"""Retrieval quality metrics independent of any retriever (Phase 4.8)."""

from __future__ import annotations

from productiq.exceptions.base import LexicalRetrievalError


def validate_positive_k(k: int) -> int:
    if k <= 0:
        msg = "K must be a positive integer"
        raise LexicalRetrievalError(msg)
    return k


def normalize_retrieved_product_ids(
    retrieved_product_ids: tuple[str, ...] | list[str],
    *,
    max_count: int | None = None,
) -> tuple[str, ...]:
    """Deduplicate retrieved IDs preserving first occurrence order."""
    seen: set[str] = set()
    normalized: list[str] = []
    for raw in retrieved_product_ids:
        product_id = str(raw).strip()
        if not product_id:
            msg = "retrieved product_id must not be empty"
            raise LexicalRetrievalError(msg)
        if product_id in seen:
            continue
        seen.add(product_id)
        normalized.append(product_id)
        if max_count is not None and len(normalized) >= max_count:
            break
    return tuple(normalized)


def normalize_relevant_product_ids(
    relevant_product_ids: tuple[str, ...] | list[str] | set[str] | frozenset[str],
) -> frozenset[str]:
    """Normalize judged relevant IDs to a set (duplicates ignored deterministically)."""
    seen: set[str] = set()
    for raw in relevant_product_ids:
        product_id = str(raw).strip()
        if not product_id:
            msg = "relevant product_id must not be empty"
            raise LexicalRetrievalError(msg)
        seen.add(product_id)
    return frozenset(seen)


def count_relevant_in_prefix(
    retrieved_product_ids: tuple[str, ...],
    relevant_product_ids: frozenset[str],
    *,
    k: int,
) -> int:
    validate_positive_k(k)
    prefix = retrieved_product_ids[:k]
    return sum(1 for product_id in prefix if product_id in relevant_product_ids)


def precision_at_k(
    retrieved_product_ids: tuple[str, ...] | list[str],
    relevant_product_ids: tuple[str, ...] | list[str] | set[str] | frozenset[str],
    *,
    k: int,
) -> float:
    """Precision@K: relevant in top-K divided by effective denominator.

    Denominator is ``min(K, len(retrieved))`` when at least one result exists;
    otherwise 0.0 (no retrieved results to evaluate).
    """
    validate_positive_k(k)
    retrieved = normalize_retrieved_product_ids(retrieved_product_ids, max_count=k)
    relevant = normalize_relevant_product_ids(relevant_product_ids)
    if not retrieved:
        return 0.0
    hits = count_relevant_in_prefix(retrieved, relevant, k=k)
    denominator = min(k, len(retrieved))
    return hits / denominator


def recall_at_k(
    retrieved_product_ids: tuple[str, ...] | list[str],
    relevant_product_ids: tuple[str, ...] | list[str] | set[str] | frozenset[str],
    *,
    k: int,
) -> float | None:
    """Recall@K: relevant in top-K divided by total judged relevant count.

    Returns ``None`` when the judged relevance set is empty (undefined recall).
    """
    validate_positive_k(k)
    retrieved = normalize_retrieved_product_ids(retrieved_product_ids, max_count=k)
    relevant = normalize_relevant_product_ids(relevant_product_ids)
    if not relevant:
        return None
    hits = count_relevant_in_prefix(retrieved, relevant, k=k)
    return hits / len(relevant)


def reciprocal_rank(
    retrieved_product_ids: tuple[str, ...] | list[str],
    relevant_product_ids: tuple[str, ...] | list[str] | set[str] | frozenset[str],
) -> tuple[float, int | None]:
    """MRR per-query reciprocal rank and 1-based rank of first relevant hit."""
    retrieved = normalize_retrieved_product_ids(retrieved_product_ids)
    relevant = normalize_relevant_product_ids(relevant_product_ids)
    for index, product_id in enumerate(retrieved, start=1):
        if product_id in relevant:
            return 1.0 / index, index
    return 0.0, None


def mean_reciprocal_rank(reciprocal_ranks: tuple[float, ...] | list[float]) -> float:
    if not reciprocal_ranks:
        msg = "reciprocal_ranks must not be empty"
        raise LexicalRetrievalError(msg)
    return sum(reciprocal_ranks) / len(reciprocal_ranks)


def macro_mean(values: tuple[float, ...] | list[float]) -> float:
    if not values:
        msg = "macro_mean requires at least one value"
        raise LexicalRetrievalError(msg)
    return sum(values) / len(values)


__all__ = [
    "count_relevant_in_prefix",
    "macro_mean",
    "mean_reciprocal_rank",
    "normalize_relevant_product_ids",
    "normalize_retrieved_product_ids",
    "precision_at_k",
    "recall_at_k",
    "reciprocal_rank",
    "validate_positive_k",
]
