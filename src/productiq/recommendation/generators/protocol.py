"""Recommendation candidate generator protocol (Phase 11.2)."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from productiq.recommendation.contracts import RecommendationCandidate, RecommendationRequest
from productiq.representation.schema import ProductRepresentation


@runtime_checkable
class RecommendationCandidateGenerator(Protocol):
    """Generate recommendation candidates for one seed product."""

    def generate(
        self,
        request: RecommendationRequest,
        seed_product: ProductRepresentation,
    ) -> tuple[RecommendationCandidate, ...]:
        """Return up to ``candidate_pool_top_k`` candidates excluding the seed when possible."""


__all__ = ["RecommendationCandidateGenerator"]
