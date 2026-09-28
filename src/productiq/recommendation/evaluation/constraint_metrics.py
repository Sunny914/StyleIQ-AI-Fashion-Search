"""Constraint compliance metrics for recommendation evaluation (Phase 11.7)."""

from __future__ import annotations

from collections.abc import Sequence

from productiq.recommendation.contracts import RankedRecommendation
from productiq.recommendation.selection_context import RecommendationSelectionContext
from productiq.recommendation.selection_diagnostics import RecommendationSelectionRejectionReason
from productiq.recommendation.selection_keys import diversity_brand_key, diversity_product_type_key


def seed_leakage_detected(
    *,
    seed_product_id: str | None,
    recommendations: Sequence[RankedRecommendation],
) -> bool:
    if seed_product_id is None:
        return False
    return any(row.product_id == seed_product_id for row in recommendations)


def duplicate_recommendation_count(recommendations: Sequence[RankedRecommendation]) -> int:
    seen: set[str] = set()
    duplicates = 0
    for row in recommendations:
        if row.product_id in seen:
            duplicates += 1
        else:
            seen.add(row.product_id)
    return duplicates


def max_per_brand_violation_count(
    product_ids: Sequence[str],
    *,
    context: RecommendationSelectionContext,
    max_per_brand: int,
) -> int:
    counts: dict[str, int] = {}
    violations = 0
    for product_id in product_ids:
        filtering = context.filtering_by_product_id.get(product_id)
        product = context.product_by_product_id.get(product_id)
        brand_key = diversity_brand_key(filtering=filtering, product=product)
        if brand_key is None:
            continue
        counts[brand_key] = counts.get(brand_key, 0) + 1
        if counts[brand_key] > max_per_brand:
            violations += 1
    return violations


def max_per_product_type_violation_count(
    product_ids: Sequence[str],
    *,
    context: RecommendationSelectionContext,
    max_per_product_type: int,
) -> int:
    counts: dict[str, int] = {}
    violations = 0
    for product_id in product_ids:
        filtering = context.filtering_by_product_id.get(product_id)
        product = context.product_by_product_id.get(product_id)
        type_key = diversity_product_type_key(filtering=filtering, product=product)
        if type_key is None:
            continue
        counts[type_key] = counts.get(type_key, 0) + 1
        if counts[type_key] > max_per_product_type:
            violations += 1
    return violations


def count_constraint_rejections(
    *,
    reason: RecommendationSelectionRejectionReason,
    diagnostics: Sequence[object],
) -> int:
    count = 0
    for row in diagnostics:
        decision_reason = getattr(row, "reason", None)
        if decision_reason == reason:
            count += 1
    return count


__all__ = [
    "count_constraint_rejections",
    "duplicate_recommendation_count",
    "max_per_brand_violation_count",
    "max_per_product_type_violation_count",
    "seed_leakage_detected",
]
