"""Candidate coverage for ranking evaluation (Phase 10.6)."""

from __future__ import annotations

from productiq.retrieval.evaluation.metrics import normalize_relevant_product_ids


def candidate_coverage_ratio(
    *,
    judged_relevant_product_ids: tuple[str, ...] | list[str],
    candidate_pool_product_ids: tuple[str, ...] | list[str],
) -> float | None:
    """Return |relevant ∩ pool| / |relevant|; ``None`` when judged set is empty."""
    judged = normalize_relevant_product_ids(judged_relevant_product_ids)
    if not judged:
        return None
    pool = frozenset(candidate_pool_product_ids)
    return len(judged & pool) / len(judged)


__all__ = ["candidate_coverage_ratio"]
