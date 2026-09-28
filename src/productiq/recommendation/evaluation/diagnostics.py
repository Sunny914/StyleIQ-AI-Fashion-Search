"""Recommendation evaluation diagnostics and failure observations (Phase 11.7)."""

from __future__ import annotations

from enum import StrEnum

from productiq.ranking.evaluation.coverage import candidate_coverage_ratio


class RecommendationFailureObservation(StrEnum):
    """Diagnostic observations (not proven root causes)."""

    NO_RELEVANT_RETRIEVED = "NO_RELEVANT_RETRIEVED"
    RELEVANT_IN_CANDIDATE_POOL_BUT_NOT_TOP_K = "RELEVANT_IN_CANDIDATE_POOL_BUT_NOT_TOP_K"
    RELEVANT_SELECTED_BEFORE_CONSTRAINTS = "RELEVANT_SELECTED_BEFORE_CONSTRAINTS"
    RELEVANT_DROPPED_BY_CONSTRAINT = "RELEVANT_DROPPED_BY_CONSTRAINT"
    INSUFFICIENT_CANDIDATES = "INSUFFICIENT_CANDIDATES"
    SHORTFALL = "SHORTFALL"


def observe_seed_failures(
    *,
    relevance_grades: dict[str, int],
    min_relevant_grade: int,
    requested_top_k: int,
    candidate_pool_product_ids: tuple[str, ...],
    ranked_product_ids: tuple[str, ...],
    final_product_ids: tuple[str, ...],
    evaluation_k: int,
    relevant_dropped_by_constraint_product_ids: tuple[str, ...] = (),
) -> tuple[RecommendationFailureObservation, ...]:
    """Classify observable pipeline outcomes for one seed (deterministic)."""
    relevant = {
        product_id
        for product_id, grade in relevance_grades.items()
        if grade >= min_relevant_grade
    }
    observations: list[RecommendationFailureObservation] = []
    final_prefix = final_product_ids[:evaluation_k]
    if not any(product_id in relevant for product_id in final_prefix):
        observations.append(RecommendationFailureObservation.NO_RELEVANT_RETRIEVED)
    pool_coverage = candidate_coverage_ratio(
        judged_relevant_product_ids=tuple(relevant),
        candidate_pool_product_ids=candidate_pool_product_ids,
    )
    if pool_coverage is not None and pool_coverage < 1.0:
        missing_in_pool = relevant - frozenset(candidate_pool_product_ids)
        if missing_in_pool:
            observations.append(RecommendationFailureObservation.INSUFFICIENT_CANDIDATES)
    ranked_prefix = ranked_product_ids[:evaluation_k]
    if (
        candidate_pool_product_ids
        and (relevant & frozenset(candidate_pool_product_ids))
        and not any(product_id in relevant for product_id in ranked_prefix)
    ):
        observations.append(
            RecommendationFailureObservation.RELEVANT_IN_CANDIDATE_POOL_BUT_NOT_TOP_K
        )
    if relevant_dropped_by_constraint_product_ids:
        observations.append(RecommendationFailureObservation.RELEVANT_DROPPED_BY_CONSTRAINT)
    elif relevant & frozenset(ranked_prefix) and not any(
        product_id in relevant for product_id in final_prefix
    ):
        observations.append(RecommendationFailureObservation.RELEVANT_SELECTED_BEFORE_CONSTRAINTS)
    shortfall = max(requested_top_k - len(final_product_ids), 0)
    if shortfall > 0:
        observations.append(RecommendationFailureObservation.SHORTFALL)
    return tuple(dict.fromkeys(observations))


__all__ = [
    "RecommendationFailureObservation",
    "observe_seed_failures",
]
