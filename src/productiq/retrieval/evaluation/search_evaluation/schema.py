"""Search evaluation version constants (Phase 12.1)."""

from __future__ import annotations

SEARCH_EVALUATION_CONTRACT_VERSION = "12.1.0"

MIN_SEARCH_RELEVANCE_GRADE = 0
MAX_SEARCH_RELEVANCE_GRADE = 3

SUPPORTED_SEARCH_METRIC_FAMILIES: tuple[str, ...] = (
    "precision_at_k",
    "recall_at_k",
    "hit_rate_at_k",
    "mrr",
    "ndcg_at_k",
)

__all__ = [
    "MAX_SEARCH_RELEVANCE_GRADE",
    "MIN_SEARCH_RELEVANCE_GRADE",
    "SEARCH_EVALUATION_CONTRACT_VERSION",
    "SUPPORTED_SEARCH_METRIC_FAMILIES",
]
