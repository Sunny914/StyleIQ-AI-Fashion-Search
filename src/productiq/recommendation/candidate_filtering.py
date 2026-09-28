"""Apply recommendation hard constraints to candidate pools (Phase 11.2)."""

from __future__ import annotations

from collections.abc import Mapping

from productiq.exceptions.base import CatalogValidationError
from productiq.recommendation.contracts import RecommendationCandidate
from productiq.representation.filtering import FilteringRepresentation
from productiq.representation.query_contract import QueryFilterConstraints
from productiq.retrieval.catalog_constraint_match import (
    constraints_are_active,
    filtering_satisfies_query_constraints,
)


def filter_recommendation_candidates(
    candidates: tuple[RecommendationCandidate, ...],
    *,
    constraints: QueryFilterConstraints | None,
    filtering_by_product_id: Mapping[str, FilteringRepresentation],
) -> tuple[RecommendationCandidate, ...]:
    """Filter candidates using ``QueryFilterConstraints`` semantics (preserve order)."""
    if constraints is None or not constraints_are_active(constraints):
        return candidates
    kept: list[RecommendationCandidate] = []
    for candidate in candidates:
        filtering = filtering_by_product_id.get(candidate.product_id)
        if filtering is None:
            msg = f"filtering metadata missing for candidate product_id {candidate.product_id!r}"
            raise CatalogValidationError(msg)
        if filtering_satisfies_query_constraints(filtering, constraints):
            kept.append(candidate)
    return tuple(kept)


__all__ = ["filter_recommendation_candidates"]
