"""Recommendation evaluation metrics (Phase 11.7)."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import TypedDict

from productiq.exceptions.base import RecommendationError
from productiq.recommendation.evaluation.benchmark_schema import MAX_RELEVANCE_GRADE
from productiq.retrieval.evaluation.metrics import (
    count_relevant_in_prefix,
    macro_mean,
    normalize_retrieved_product_ids,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
    validate_positive_k,
)


def judged_relevant_product_ids(
    relevance_grades: Mapping[str, int],
    *,
    min_relevant_grade: int,
) -> frozenset[str]:
    return frozenset(
        product_id
        for product_id, grade in relevance_grades.items()
        if grade >= min_relevant_grade
    )


def hit_rate_at_k(
    retrieved_product_ids: Sequence[str],
    relevance_grades: Mapping[str, int],
    *,
    k: int,
    min_relevant_grade: int,
) -> float:
    """1.0 when at least one judged-relevant item appears in top-K; else 0.0."""
    validate_positive_k(k)
    relevant = judged_relevant_product_ids(relevance_grades, min_relevant_grade=min_relevant_grade)
    if not relevant:
        return 0.0
    hits = count_relevant_in_prefix(
        normalize_retrieved_product_ids(tuple(retrieved_product_ids), max_count=k),
        relevant,
        k=k,
    )
    return 1.0 if hits > 0 else 0.0


def _dcg_at_k(gains: Sequence[float], *, k: int) -> float:
    total = 0.0
    for index, gain in enumerate(gains[:k], start=1):
        if index == 1:
            total += gain
        else:
            total += gain / math.log2(index + 1)
    return total


def ndcg_at_k(
    retrieved_product_ids: Sequence[str],
    relevance_grades: Mapping[str, int],
    *,
    k: int,
) -> float | None:
    """nDCG@K using graded gains (0..3). Returns None when all ideal gains are zero."""
    validate_positive_k(k)
    retrieved = normalize_retrieved_product_ids(tuple(retrieved_product_ids), max_count=k)
    if not retrieved:
        return 0.0
    gains = [float(relevance_grades.get(product_id, 0)) for product_id in retrieved]
    ideal = sorted(relevance_grades.values(), reverse=True)
    ideal_gains = [float(value) for value in ideal[:k]]
    idcg = _dcg_at_k(ideal_gains, k=k)
    if idcg == 0.0:
        return None
    return _dcg_at_k(gains, k=k) / idcg


def recommendation_catalog_coverage(
    recommended_product_ids: Sequence[str],
    *,
    eligible_catalog_product_count: int,
) -> float | None:
    if eligible_catalog_product_count <= 0:
        return None
    unique = len(set(recommended_product_ids))
    return unique / eligible_catalog_product_count


def unique_ratio(values: Sequence[str | None]) -> float | None:
    present = [value for value in values if value is not None]
    if not present:
        return None
    return len(set(present)) / len(present)


def shortfall_metrics(*, requested_top_k: int, returned_count: int) -> tuple[int, float]:
    if requested_top_k < 0:
        msg = "requested_top_k must be non-negative"
        raise RecommendationError(msg)
    if returned_count < 0:
        msg = "returned_count must be non-negative"
        raise RecommendationError(msg)
    shortfall = max(requested_top_k - returned_count, 0)
    rate = shortfall / requested_top_k if requested_top_k > 0 else 0.0
    return shortfall, rate


def validate_relevance_grades_map(grades: Mapping[str, int]) -> None:
    for product_id, grade in grades.items():
        if not product_id.strip():
            msg = "relevance grade product_id must not be empty"
            raise RecommendationError(msg)
        if grade < 0 or grade > MAX_RELEVANCE_GRADE:
            msg = f"relevance grade must be in [0, {MAX_RELEVANCE_GRADE}]"
            raise RecommendationError(msg)


class RelevanceMetricsAtK(TypedDict):
    precision_at_k: float
    recall_at_k: float | None
    hit_rate_at_k: float
    ndcg_at_k: float | None
    reciprocal_rank: float


def compute_relevance_metrics_at_k(
    retrieved_product_ids: Sequence[str],
    relevance_grades: Mapping[str, int],
    *,
    k: int,
    min_relevant_grade: int,
) -> RelevanceMetricsAtK:
    relevant = judged_relevant_product_ids(relevance_grades, min_relevant_grade=min_relevant_grade)
    retrieved = normalize_retrieved_product_ids(tuple(retrieved_product_ids), max_count=k)
    precision = precision_at_k(retrieved, relevant, k=k)
    recall = recall_at_k(retrieved, relevant, k=k)
    hit = hit_rate_at_k(
        retrieved,
        relevance_grades,
        k=k,
        min_relevant_grade=min_relevant_grade,
    )
    ndcg = ndcg_at_k(retrieved, relevance_grades, k=k)
    rr = reciprocal_rank(retrieved, relevant)[0]
    return {
        "precision_at_k": precision,
        "recall_at_k": recall,
        "hit_rate_at_k": hit,
        "ndcg_at_k": ndcg,
        "reciprocal_rank": rr,
    }


__all__ = [
    "RelevanceMetricsAtK",
    "compute_relevance_metrics_at_k",
    "hit_rate_at_k",
    "judged_relevant_product_ids",
    "macro_mean",
    "ndcg_at_k",
    "precision_at_k",
    "recall_at_k",
    "recommendation_catalog_coverage",
    "shortfall_metrics",
    "unique_ratio",
    "validate_relevance_grades_map",
]
